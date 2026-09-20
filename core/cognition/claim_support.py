"""Layer 72 — bounded claim-to-quote alignment gate.

Layers 70–71 prove that a Deep Recall block covers the right requested part
with a validated quote from the right frozen evidence excerpt. They still do
not prove that the block's full factual sentence follows from that quote.

Layer 72 adds a second, bounded model pass over only citation-gate-passing fact
blocks. The checker receives the claim and its already-validated exact quotes,
uses no external knowledge, and classifies the block as supported, partial,
unsupported or contradicted. Partial/unsupported/contradicted fact blocks are
converted to an explicit unknown before publication and before coverage is
measured.

This is a claim/quote alignment check, not independent truth certification.
"""
from __future__ import annotations

from hashlib import sha256
import json

from core.cognition.evidence_evaluation import normalise
from core.cognition.model_independence import build_model_request, invoke_model


BLOCKING_VERDICTS = {"partial", "unsupported", "contradicted"}
ALLOWED_VERDICTS = {"supported", *BLOCKING_VERDICTS}


def _raw_blocks(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
        blocks = data.get("blocks")
        return blocks if isinstance(blocks, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _accepted_quote_pairs(block: dict, audit_item: dict) -> list[dict]:
    accepted = {
        (
            str(item.get("source") or "").strip(),
            str(item.get("quote_sha256") or "").strip(),
        )
        for item in audit_item.get("citations", [])
        if isinstance(item, dict)
        and item.get("source")
        and item.get("quote_sha256")
    }
    pairs = []
    citations = block.get("citations", [])
    if not isinstance(citations, list):
        return pairs
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        source = str(citation.get("source") or "").strip()
        quote = citation.get("quote")
        if not source or not isinstance(quote, str) or not normalise(quote):
            continue
        quote_hash = sha256(normalise(quote).encode()).hexdigest()
        if (source, quote_hash) not in accepted:
            continue
        pairs.append({"source": source, "quote": quote})
    return pairs


def build_claim_support_payload(raw: str, evidence_audit: dict | None) -> list[dict]:
    """Return only fact blocks whose citations already passed the hard gate."""
    blocks = _raw_blocks(raw)
    checks = {
        int(item.get("block")): item
        for item in (evidence_audit or {}).get("checks", [])
        if isinstance(item, dict)
        and item.get("passed")
        and str(item.get("block") or "").isdigit()
    }
    payload = []
    for number, block in enumerate(blocks, 1):
        if not isinstance(block, dict) or block.get("kind") != "fact":
            continue
        check = checks.get(number)
        if not check:
            continue
        quotes = _accepted_quote_pairs(block, check)
        if not quotes:
            continue
        text = block.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        payload.append({
            "block": number,
            "claim": text.strip(),
            "evidence": quotes,
        })
    return payload


def evaluate_claim_support(
    raw: str,
    evidence_audit: dict | None,
    model_adapter,
) -> dict:
    """Run one bounded claim/quote alignment pass.

    The checker may only judge whether the supplied quotes support the supplied
    claim. It is not permitted to retrieve, rewrite or use outside knowledge.
    """
    candidates = build_claim_support_payload(raw, evidence_audit)
    audit = {
        "version": "1.0",
        "status": "not_required" if not candidates else "unavailable",
        "checked_blocks": len(candidates),
        "failed_blocks": [],
        "checks": [],
        "independent_truth_certification": False,
        "scope": "claim_to_validated_quote_alignment_only",
    }
    if not candidates:
        return audit

    system = """You are Project L's bounded claim-to-quote alignment checker.
Use ONLY the exact evidence quotes supplied in the user payload. Do not use
outside knowledge, memory, plausibility or unstated implications.

For each block classify the WHOLE factual claim:
- supported: every material factual clause is established by the supplied quotes.
- partial: at least one material clause is supported but another material clause is not.
- unsupported: the quotes do not establish the claim.
- contradicted: the quotes materially state the opposite.

Paraphrase is allowed when meaning is preserved. Dates, numbers, negation,
speaker identity, plan-vs-outcome status and causal wording must not be silently
strengthened. Return JSON only:
{"blocks":[{"block":1,"verdict":"supported|partial|unsupported|contradicted",
"reason":"brief evidence-only reason"}]}.
Do not rewrite the answer and do not add facts."""

    request = build_model_request(
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {"blocks": candidates},
                    ensure_ascii=False,
                ),
            },
        ],
        purpose="l_deep_recall_claim_quote_alignment",
        routing_purpose="l_recall_response",
        response_format={"type": "json_object"},
        temperature=0.0,
        max_output_tokens=3000,
    )

    try:
        result = invoke_model(model_adapter, request)
        data = json.loads(result["content"])
        verdicts = data.get("blocks")
        if not isinstance(verdicts, list):
            raise ValueError("invalid_claim_support_schema")

        by_block = {}
        for item in verdicts:
            if not isinstance(item, dict):
                continue
            try:
                number = int(item.get("block"))
            except (TypeError, ValueError):
                continue
            verdict = str(item.get("verdict") or "").strip().lower()
            if verdict not in ALLOWED_VERDICTS:
                continue
            by_block[number] = {
                "block": number,
                "verdict": verdict,
                "reason": str(item.get("reason") or "")[:500],
            }

        checks = []
        failed = []
        for candidate in candidates:
            number = candidate["block"]
            item = by_block.get(number)
            if item is None:
                item = {
                    "block": number,
                    "verdict": "unavailable",
                    "reason": "checker_returned_no_valid_verdict",
                }
            checks.append(item)
            if item["verdict"] in BLOCKING_VERDICTS:
                failed.append(number)

        missing = [item for item in checks if item["verdict"] == "unavailable"]
        audit.update(
            status=(
                "unavailable" if missing
                else "partial" if failed
                else "passed"
            ),
            failed_blocks=failed,
            checks=checks,
            model_id=result.get("model_id"),
        )
        return audit
    except Exception as exc:
        audit.update(
            status="unavailable",
            error_type=type(exc).__name__,
        )
        return audit


def apply_claim_support_gate(raw: str, support_audit: dict | None) -> str:
    """Convert only semantically failed fact blocks into explicit unknowns."""
    failed = {
        int(item.get("block")): str(item.get("verdict") or "")
        for item in (support_audit or {}).get("checks", [])
        if isinstance(item, dict)
        and item.get("verdict") in BLOCKING_VERDICTS
        and str(item.get("block") or "").isdigit()
    }
    if not failed:
        return raw

    try:
        data = json.loads(raw)
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            return raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return raw

    revised = []
    for number, block in enumerate(blocks, 1):
        if number not in failed or not isinstance(block, dict):
            revised.append(block)
            continue
        verdict = failed[number]
        if verdict == "contradicted":
            text = "The cited passage conflicts with this claim, so I have withheld it."
        elif verdict == "partial":
            text = "The cited passage supports only part of this claim, so I have withheld the whole claim."
        else:
            text = "The cited passage does not establish this claim, so I have withheld it."
        revised.append({
            "kind": "unknown",
            "text": text,
            "citations": [],
            "covers": [],
        })

    data["blocks"] = revised
    return json.dumps(data, ensure_ascii=False)

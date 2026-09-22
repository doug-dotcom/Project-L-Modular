"""Layers 72–76 — claim alignment, atomicity, consistency and receipt binding.

Layers 70–71 prove that a Deep Recall block covers the right requested part
with a validated quote from the right frozen evidence excerpt. They still do
not prove that the block's full factual sentence follows from that quote.

Layer 72 adds a second, bounded model pass over only citation-gate-passing fact
blocks. The checker receives the claim and its already-validated exact quotes,
uses no external knowledge, and classifies the block as supported, partial,
unsupported or contradicted. Partial/unsupported/contradicted fact blocks are
converted to an explicit unknown before publication and before coverage is
measured.

Layer 73 uses the same bounded pass to classify whether each factual block is
atomic or compound. A block is compound only when it bundles materially
independent factual propositions that should be separately verifiable; multiple
details about one event/entity may remain atomic.

Layer 74 uses that same bounded response to identify direct conflicts between
otherwise publishable fact blocks. Only materially incompatible claims about
the same event/proposition/time scope count; plan→outcome, later updates and
different dated states are not automatically conflicts. Conflicting blocks are
withheld together rather than asking the checker to choose a winner.

Layer 76 cryptographically binds this semantic receipt to both the exact raw
draft it checked and the exact post-gate publication JSON produced from it, so
the receipt cannot be replayed against a different answer.

This is a claim/quote alignment and structure check, not independent truth certification.
"""
from __future__ import annotations

from hashlib import sha256
import json

from core.cognition.evidence_evaluation import normalise
from core.cognition.model_independence import build_model_request, invoke_model


BLOCKING_VERDICTS = {"partial", "unsupported", "contradicted"}
ALLOWED_VERDICTS = {"supported", *BLOCKING_VERDICTS}
ALLOWED_ATOMICITY = {"atomic", "compound"}
ALLOWED_CONFLICT_TYPES = {"contradiction", "timeline_collision", "status_conflict"}


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
        "version": "4.0",
        "status": "not_required" if not candidates else "unavailable",
        "draft_sha256": sha256(raw.encode()).hexdigest(),
        "citation_audit_draft_sha256": str((evidence_audit or {}).get("draft_sha256") or ""),
        "publication_draft_sha256": "",
        "checked_blocks": len(candidates),
        "failed_blocks": [],
        "compound_blocks": [],
        "conflict_blocks": [],
        "conflicts": [],
        "checks": [],
        "independent_truth_certification": False,
        "scope": "claim_alignment_atomicity_and_cross_block_consistency",
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
strengthened.

Also classify ATOMICITY:
- atomic: one independently verifiable factual proposition, including multiple
  attributes of the same event/entity when they rise or fall together.
- compound: two or more materially independent factual propositions that could
  be true or false separately and should be split into separate fact blocks.

Do not call a single event with its date/place/status compound merely because it
has several details.

Also perform CROSS-BLOCK CONSISTENCY using ONLY the supplied claims and quotes.
Report a conflict only when two or more otherwise factual blocks make materially
incompatible claims about the SAME event, proposition and relevant time/scope.
Do NOT mark these as conflicts merely because they differ:
- a plan/intention followed by a later outcome,
- an earlier state followed by a later update,
- two distinct events or people,
- different dates that can both be true,
- one block being more detailed than another without incompatibility.
Do not choose which side is true.

Return JSON only:
{"blocks":[{"block":1,"verdict":"supported|partial|unsupported|contradicted",
"atomicity":"atomic|compound","reason":"brief evidence-only reason"}],
"conflicts":[{"blocks":[1,2],"type":"contradiction|timeline_collision|status_conflict",
"reason":"brief evidence-only reason"}]}.
Return "conflicts":[] when none are present. Do not rewrite the answer and do not add facts."""

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
            atomicity = str(item.get("atomicity") or "").strip().lower()
            if atomicity not in ALLOWED_ATOMICITY:
                atomicity = "unavailable"
            by_block[number] = {
                "block": number,
                "verdict": verdict,
                "atomicity": atomicity,
                "reason": str(item.get("reason") or "")[:500],
            }

        conflicts_declared = "conflicts" in data
        raw_conflicts = data.get("conflicts", [])
        parsed_conflicts = []
        conflict_blocks = []
        candidate_blocks = {candidate["block"] for candidate in candidates}
        if isinstance(raw_conflicts, list):
            seen_conflicts = set()
            for raw_conflict in raw_conflicts:
                if not isinstance(raw_conflict, dict):
                    continue
                raw_numbers = raw_conflict.get("blocks")
                if not isinstance(raw_numbers, list):
                    continue
                numbers = []
                for value in raw_numbers:
                    try:
                        number = int(value)
                    except (TypeError, ValueError):
                        continue
                    if number in candidate_blocks and number not in numbers:
                        numbers.append(number)
                if len(numbers) < 2:
                    continue
                conflict_type = str(raw_conflict.get("type") or "").strip().lower()
                if conflict_type not in ALLOWED_CONFLICT_TYPES:
                    continue
                key = (tuple(sorted(numbers)), conflict_type)
                if key in seen_conflicts:
                    continue
                seen_conflicts.add(key)
                parsed_conflicts.append({
                    "blocks": numbers,
                    "type": conflict_type,
                    "reason": str(raw_conflict.get("reason") or "")[:500],
                })
                for number in numbers:
                    if number not in conflict_blocks:
                        conflict_blocks.append(number)

        checks = []
        failed = []
        for candidate in candidates:
            number = candidate["block"]
            item = by_block.get(number)
            if item is None:
                item = {
                    "block": number,
                    "verdict": "unavailable",
                    "atomicity": "unavailable",
                    "reason": "checker_returned_no_valid_verdict",
                }
            checks.append(item)
            if item["verdict"] in BLOCKING_VERDICTS:
                failed.append(number)

        compound = [
            item["block"]
            for item in checks
            if item.get("atomicity") == "compound"
        ]
        atomicity_missing = [
            item for item in checks if item.get("atomicity") == "unavailable"
        ]
        missing = [item for item in checks if item["verdict"] == "unavailable"]
        failed_union = list(dict.fromkeys(failed + compound + conflict_blocks))
        audit.update(
            status=(
                "unavailable" if missing
                else "partial" if failed_union
                else "passed"
            ),
            failed_blocks=failed_union,
            compound_blocks=compound,
            conflict_blocks=conflict_blocks,
            conflicts=parsed_conflicts,
            atomicity_status=(
                "unavailable" if atomicity_missing
                else "partial" if compound
                else "passed"
            ),
            consistency_status=(
                "unavailable" if not conflicts_declared
                else "partial" if parsed_conflicts
                else "passed"
            ),
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


def bind_claim_support_to_publication(
    support_audit: dict | None,
    publication_raw: str,
) -> dict:
    """Bind a Layers 72–74 receipt to the exact post-gate publication JSON."""
    bound = dict(support_audit or {})
    bound["publication_draft_sha256"] = sha256(
        str(publication_raw or "").encode()
    ).hexdigest()
    return bound


def apply_claim_support_gate(raw: str, support_audit: dict | None) -> str:
    """Convert only semantically failed fact blocks into explicit unknowns."""
    failed = {}
    for item in (support_audit or {}).get("checks", []):
        if not isinstance(item, dict) or not str(item.get("block") or "").isdigit():
            continue
        number = int(item.get("block"))
        verdict = str(item.get("verdict") or "")
        atomicity = str(item.get("atomicity") or "")
        if verdict in BLOCKING_VERDICTS:
            failed[number] = verdict
        elif atomicity == "compound":
            failed[number] = "compound"

    for value in (support_audit or {}).get("conflict_blocks", []):
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        failed.setdefault(number, "cross_block_conflict")

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
        elif verdict == "compound":
            text = "This fact block bundles multiple independently verifiable claims, so I have withheld it until those claims are split."
        elif verdict == "cross_block_conflict":
            text = "Another supported passage in this answer conflicts with this claim, so I have withheld both sides until the conflict is reconciled."
        else:
            text = "The cited passage does not establish this claim, so I have withheld it."
        revised.append({
            "kind": "unknown",
            "text": text,
            "citations": [],
            "covers": [],
            "_publication_withheld": verdict,
        })

    data["blocks"] = revised
    return json.dumps(data, ensure_ascii=False)

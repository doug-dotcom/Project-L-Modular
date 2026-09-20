"""Layers 68–83 — publication repair quality, coverage and receipt-integrity gates.

Layer 67 gives Deep Recall one bounded regeneration attempt after the citation
integrity gate withholds content. Layer 68 makes that retry fail-safe: a repair
is publishable only when its evaluated citation quality improves.

Layer 69 adds structural coverage receipts. Deep Recall's frozen composition
manifest already identifies evidence-supported requested parts. The generated
JSON must now label which of those parts each publishable block covers. Repairs
may improve citation quality or structural coverage, but they may not regress
either dimension.

Layer 70 binds coverage to evidence provenance. A block may claim a frozen
represented-part label only when its validated citations include a source that
the retrieval pipeline itself associated with that part before evidence freeze.

Layer 71 binds coverage one level deeper: the validated citation quote itself
must occur inside a frozen evidence excerpt that supported the represented part.
A correct source ID with an unrelated passage no longer satisfies coverage.

Layer 75 extends repair selection across the bounded claim-support gate introduced
by Layers 72–74. A repair may not be published if it improves citations/coverage
while introducing new unsupported claims, compound fact blocks or cross-block
conflicts. Semantic-gate outages are treated as lower confidence, not as success.

Layer 76 hash-binds the live publication receipts. A repair cannot replace the
first pass unless the rendered reply, citation audit, coverage audit and bounded
claim-support receipt all identify the exact drafts they actually evaluated.

Layer 77 binds that publication chain to Layer 66's exact frozen evidence packet
and composition manifest. A stale, reconstructed or mutated frozen packet fails
closed before Deep Recall publication.

Layer 78 binds the same frozen contract to the exact Deep Recall query that
created it. A valid evidence packet cannot be replayed for a different question.

Layer 80 binds each publishable draft to the exact provider-neutral model request
that generated it. The raw model output hash must match the semantic gate's source
draft, and first-pass/repair receipts must carry their expected generation purpose.

Layer 81 binds that request to the exact Deep Recall prompt composition. The
system message must physically contain the frozen evidence contract and coverage
contract exactly once, and the resulting prompt binding travels inside Layer 80's
request hash through publication/repair selection.

Layer 82 binds the provider-specific transport payload to that same verified
request. The transport receipt is privacy-safe: only hashes, model/API identity
and verification state are retained; prompt/evidence text is not duplicated.

Layer 83 binds the return path. The adapter fingerprints the actual provider
response text immediately after the SDK call and links it to the verified
transport receipt. Publication requires that response hash to match the exact
raw generation draft that entered the claim/citation gates.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from core.cognition.evidence_evaluation import normalise


_STATUS_RANK = {
    "blocked": 0,
    "no_citations_to_check": 1,
    "partial": 2,
    "citation_checks_passed": 3,
}


def _bounded_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _unique_parts(values: Any) -> list[str]:
    parts = []
    seen = set()
    if not isinstance(values, list):
        return parts
    for value in values:
        label = str(value or "").strip()
        if label and label not in seen:
            parts.append(label)
            seen.add(label)
    return parts


def _canonical_sha256(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def composition_manifest_sha256(manifest: dict | None) -> str:
    manifest = dict(manifest or {})
    manifest.pop("manifest_sha256", None)
    return _canonical_sha256(manifest)


def frozen_evidence_packet_sha256(rows: list[dict] | None) -> str:
    return _canonical_sha256(list(rows or []))


def verify_frozen_evidence_binding(
    manifest: dict | None,
    evidence_rows: list[dict] | None,
    *,
    query: str | None = None,
) -> dict:
    """Verify Layer 66's manifest, frozen packet and optional exact query."""
    manifest = dict(manifest or {})
    expected_manifest = str(manifest.get("manifest_sha256") or "").strip()
    expected_evidence = str(manifest.get("evidence_packet_sha256") or "").strip()
    expected_query = str(manifest.get("query_sha256") or "").strip()

    # Pre-Layer-77 manifests remain readable. Layer 77 v4 manifests bind the
    # packet/manifest; Layer 78 v5 additionally binds the exact query.
    if not expected_manifest and not expected_evidence and not expected_query:
        return {
            "version": "2.0",
            "status": "legacy_unbound",
            "valid": True,
            "issues": [],
            "manifest_sha256": "",
            "evidence_packet_sha256": "",
            "request_query_sha256": "",
            "actual_request_query_sha256": "",
            "query_bound": False,
            "query_verified": False,
        }

    actual_manifest = composition_manifest_sha256(manifest)
    actual_evidence = frozen_evidence_packet_sha256(evidence_rows)
    actual_query = (
        sha256(str(query).encode("utf-8")).hexdigest()
        if query is not None else ""
    )
    issues = []
    if not expected_manifest:
        issues.append("manifest_fingerprint_missing")
    elif expected_manifest != actual_manifest:
        issues.append("manifest_fingerprint_mismatch")
    if not expected_evidence:
        issues.append("evidence_packet_fingerprint_missing")
    elif expected_evidence != actual_evidence:
        issues.append("evidence_packet_fingerprint_mismatch")
    if expected_query and query is not None and expected_query != actual_query:
        issues.append("request_query_fingerprint_mismatch")

    return {
        "version": "2.0",
        "status": "verified" if not issues else "mismatch",
        "valid": not issues,
        "issues": issues,
        "manifest_sha256": expected_manifest,
        "actual_manifest_sha256": actual_manifest,
        "evidence_packet_sha256": expected_evidence,
        "actual_evidence_packet_sha256": actual_evidence,
        "request_query_sha256": expected_query,
        "actual_request_query_sha256": actual_query,
        "query_bound": bool(expected_query),
        "query_verified": bool(
            expected_query and query is not None and expected_query == actual_query
        ),
    }


def build_deep_recall_prompt_binding(
    system_prompt: str,
    evidence_contract: str,
    coverage_contract_text: str,
    frozen_binding: dict | None,
) -> dict:
    """Bind exact Deep Recall prompt composition to the frozen evidence receipt."""
    system_prompt = str(system_prompt or "")
    evidence_contract = str(evidence_contract or "")
    coverage_contract_text = str(coverage_contract_text or "")
    frozen_binding = dict(frozen_binding or {})
    issues = []

    if not frozen_binding.get("valid"):
        issues.append("frozen_binding_invalid")
    if not evidence_contract or system_prompt.count(evidence_contract) != 1:
        issues.append("evidence_contract_not_exactly_once")
    if not coverage_contract_text or system_prompt.count(coverage_contract_text) != 1:
        issues.append("coverage_contract_not_exactly_once")

    binding = {
        "version": "1.0",
        "status": "verified" if not issues else "mismatch",
        "valid": not issues,
        "system_prompt_sha256": sha256(system_prompt.encode("utf-8")).hexdigest(),
        "evidence_contract_sha256": sha256(
            evidence_contract.encode("utf-8")
        ).hexdigest(),
        "coverage_contract_sha256": sha256(
            coverage_contract_text.encode("utf-8")
        ).hexdigest(),
        "manifest_sha256": str(
            frozen_binding.get("actual_manifest_sha256")
            or frozen_binding.get("manifest_sha256")
            or ""
        ),
        "evidence_packet_sha256": str(
            frozen_binding.get("actual_evidence_packet_sha256")
            or frozen_binding.get("evidence_packet_sha256")
            or ""
        ),
        "query_sha256": str(
            frozen_binding.get("request_query_sha256") or ""
        ),
        "issues": issues,
    }
    binding["binding_sha256"] = _canonical_sha256(binding)
    return binding


def coverage_contract(manifest: dict | None) -> str:
    """Return the Layers 69–70 structural/evidence coverage contract."""
    manifest = dict(manifest or {})
    represented = _unique_parts(manifest.get("represented_parts"))
    if not represented:
        return "DEEP RECALL COVERAGE RECEIPT: no represented parts require structural coverage labelling."

    raw_bindings = manifest.get("part_sources")
    binding_available = isinstance(raw_bindings, dict)
    bindings = {
        part: _unique_parts(raw_bindings.get(part))[:20]
        for part in represented
    } if binding_available else {}

    contract = (
        "DEEP RECALL COVERAGE RECEIPT — for this Deep Recall only, every answer block "
        "must include a \"covers\" array. Each covers value must be copied exactly from "
        "the represented-part labels below. A represented part counts as covered only when "
        "it appears on a block that passes the citation-integrity gate; unknown blocks do "
        "not satisfy supported-part coverage. Use [] when a block does not cover one of "
        "these parts. Do not invent or paraphrase labels. Represented parts: "
        + json.dumps(represented, ensure_ascii=False)
    )
    if binding_available:
        contract += (
            "\nLAYER 70 EVIDENCE BINDING: a covers label is valid only when that same "
            "block has a validated citation from one of the frozen supporting source IDs "
            "mapped to that represented part. Do not attach a part label to an unrelated "
            "fact merely to satisfy coverage. Frozen part-to-source bindings: "
            + json.dumps(bindings, ensure_ascii=False)
        )
    if isinstance(manifest.get("part_evidence"), dict):
        contract += (
            "\nLAYER 71 QUOTE BINDING: source identity alone is not enough. The exact "
            "continuous quote used by the block must occur inside one of the frozen "
            "evidence excerpts that supported that represented part."
        )
    return contract


def evaluate_publication_coverage(
    raw: str,
    evidence_audit: dict | None,
    manifest: dict | None,
    *,
    evidence_rows: list[dict] | None = None,
) -> dict:
    """Measure structural coverage using only publishable evaluated blocks.

    This is deliberately not a semantic truth detector. The model may only claim
    exact labels issued by the frozen composition manifest, and only labels on
    citation-gate-passing non-unknown blocks count toward coverage.
    """
    manifest = dict(manifest or {})
    frozen_binding = verify_frozen_evidence_binding(manifest, evidence_rows)
    expected = _unique_parts(manifest.get("represented_parts"))
    raw_bindings = manifest.get("part_sources")
    binding_available = isinstance(raw_bindings, dict)
    allowed_sources = {
        part: set(_unique_parts(raw_bindings.get(part)))
        for part in expected
    } if binding_available else {}

    raw_excerpt_bindings = manifest.get("part_evidence")
    quote_binding_declared = isinstance(raw_excerpt_bindings, dict)
    frozen_excerpt_bindings = {
        part: {
            (
                str(item.get("source") or "").strip(),
                str(item.get("excerpt_sha256") or "").strip(),
            )
            for item in (raw_excerpt_bindings.get(part) or [])
            if isinstance(item, dict)
            and item.get("source")
            and item.get("excerpt_sha256")
        }
        for part in expected
    } if quote_binding_declared else {}

    evidence_by_binding = {}
    if quote_binding_declared:
        for row in evidence_rows or []:
            if not isinstance(row, dict):
                continue
            source = str(row.get("source") or "").strip()
            excerpt = row.get("quote_source")
            if not source or not isinstance(excerpt, str):
                continue
            fingerprint = sha256(excerpt.encode("utf-8")).hexdigest()
            evidence_by_binding.setdefault((source, fingerprint), []).append(excerpt)

    audit = {
        "version": "4.0" if quote_binding_declared else "2.0" if binding_available else "1.0",
        "draft_sha256": sha256(str(raw or "").encode()).hexdigest(),
        "status": "not_required" if not expected else "partial",
        "expected_parts": expected,
        "expected_count": len(expected),
        "covered_parts": [],
        "covered_count": 0,
        "missing_parts": list(expected),
        "missing_count": len(expected),
        "invalid_labels": [],
        "invalid_blocks": [],
        "evidence_bound": binding_available,
        "source_mismatches": [],
        "quote_bound": quote_binding_declared,
        "quote_mismatches": [],
        "frozen_evidence_binding": frozen_binding,
        "complete": not expected,
    }
    if not frozen_binding.get("valid"):
        audit.update(
            status="blocked",
            complete=False,
        )
        return audit
    if not expected:
        return audit

    passed_blocks = set()
    passed_block_sources = {}
    passed_block_citations = {}
    for item in (evidence_audit or {}).get("checks", []):
        if not isinstance(item, dict) or not item.get("passed"):
            continue
        number = _bounded_int(item.get("block"))
        passed_blocks.add(number)
        source_citations = {
            str(citation.get("source") or "").strip()
            for citation in item.get("citations", [])
            if isinstance(citation, dict) and citation.get("source")
        }
        citations = {
            (
                str(citation.get("source") or "").strip(),
                str(citation.get("quote_sha256") or "").strip(),
            )
            for citation in item.get("citations", [])
            if isinstance(citation, dict)
            and citation.get("source")
            and citation.get("quote_sha256")
        }
        passed_block_citations[number] = citations
        passed_block_sources[number] = source_citations

    try:
        data = json.loads(raw)
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError("invalid_blocks")
    except (ValueError, TypeError, json.JSONDecodeError):
        audit["invalid_blocks"] = ["invalid_answer_schema"]
        return audit

    expected_set = set(expected)
    covered = []
    covered_set = set()
    invalid_labels = []
    invalid_blocks = []
    source_mismatches = []
    quote_mismatches = []

    for number, block in enumerate(blocks, 1):
        if number not in passed_blocks or not isinstance(block, dict):
            continue
        if block.get("kind") == "unknown":
            continue

        covers = block.get("covers", [])
        if not isinstance(covers, list):
            invalid_blocks.append(number)
            continue

        raw_citations = block.get("citations", [])
        validated_quotes = []
        if isinstance(raw_citations, list):
            accepted = passed_block_citations.get(number, set())
            for citation in raw_citations:
                if not isinstance(citation, dict):
                    continue
                source = str(citation.get("source") or "").strip()
                quote = citation.get("quote")
                if not source or not isinstance(quote, str) or not normalise(quote):
                    continue
                quote_hash = sha256(normalise(quote).encode("utf-8")).hexdigest()
                if (source, quote_hash) in accepted:
                    validated_quotes.append((source, quote))

        for value in covers:
            label = str(value or "").strip()
            if not label:
                continue
            if label not in expected_set:
                if label not in invalid_labels:
                    invalid_labels.append(label)
                continue

            if binding_available:
                cited_sources = passed_block_sources.get(number, set())
                permitted_sources = allowed_sources.get(label, set())
                if not cited_sources.intersection(permitted_sources):
                    source_mismatches.append({
                        "block": number,
                        "part": label,
                        "cited_sources": sorted(cited_sources)[:8],
                        "allowed_sources": sorted(permitted_sources)[:12],
                    })
                    continue

            if quote_binding_declared:
                permitted_bindings = frozen_excerpt_bindings.get(label, set())
                quote_supported = False
                for source, quote in validated_quotes:
                    for binding in permitted_bindings:
                        if source != binding[0]:
                            continue
                        for excerpt in evidence_by_binding.get(binding, []):
                            if normalise(quote) in normalise(excerpt):
                                quote_supported = True
                                break
                        if quote_supported:
                            break
                    if quote_supported:
                        break
                if not quote_supported:
                    quote_mismatches.append({
                        "block": number,
                        "part": label,
                        "validated_sources": sorted(
                            {source for source, _quote in validated_quotes}
                        )[:8],
                        "bound_excerpt_count": len(permitted_bindings),
                    })
                    continue

            if label not in covered_set:
                covered.append(label)
                covered_set.add(label)

    missing = [part for part in expected if part not in covered_set]
    audit.update(
        status="complete" if not missing else "partial",
        covered_parts=covered,
        covered_count=len(covered),
        missing_parts=missing,
        missing_count=len(missing),
        invalid_labels=invalid_labels,
        invalid_blocks=invalid_blocks,
        source_mismatches=source_mismatches,
        source_mismatch_count=len(source_mismatches),
        quote_mismatches=quote_mismatches,
        quote_mismatch_count=len(quote_mismatches),
        complete=not missing,
    )
    return audit


def publication_quality(audit: dict | None) -> tuple[int, int, int, int]:
    """Return a deterministic citation-quality tuple. Higher is better."""
    audit = dict(audit or {})
    status_rank = _STATUS_RANK.get(str(audit.get("status") or ""), -1)
    withheld = _bounded_int(audit.get("blocks_withheld"))
    citations = _bounded_int(audit.get("citations_checked"))
    blocks = _bounded_int(audit.get("blocks_checked"))
    published = max(0, blocks - withheld)
    return status_rank, -withheld, citations, published


def coverage_quality(coverage: dict | None) -> tuple[int, int, int, int]:
    """Return a deterministic Layer 69 coverage-quality tuple."""
    coverage = dict(coverage or {})
    if coverage.get("status") == "not_required":
        return 1, 0, 0, 0
    complete = 1 if coverage.get("complete") else 0
    covered = _bounded_int(coverage.get("covered_count"))
    missing = _bounded_int(coverage.get("missing_count"))
    invalid = (
        len(coverage.get("invalid_labels") or [])
        + len(coverage.get("invalid_blocks") or [])
        + _bounded_int(coverage.get("source_mismatch_count"))
        + _bounded_int(coverage.get("quote_mismatch_count"))
    )
    return complete, covered, -missing, -invalid


def claim_support_quality(audit: dict | None) -> tuple[int, int, int, int] | None:
    """Return bounded Layers 72–74 publication quality. Higher is safer.

    None preserves pre-Layer-72 behaviour when no claim-support receipt exists.
    Passed/not_required are strongest for publication; partial means the failed
    blocks were explicitly gated and is therefore safer than unavailable, where
    claims could not be checked. Within partial results, fewer failed,
    conflicting and compound blocks are better.
    """
    if not isinstance(audit, dict) or not audit:
        return None
    status = str(audit.get("status") or "").strip().lower()
    rank = {
        "unavailable": 0,
        "partial": 2,
        "not_required": 3,
        "passed": 3,
    }.get(status, -1)
    failed = len(set(
        _bounded_int(value)
        for value in audit.get("failed_blocks", [])
        if _bounded_int(value)
    ))
    conflicts = len(set(
        _bounded_int(value)
        for value in audit.get("conflict_blocks", [])
        if _bounded_int(value)
    ))
    compound = len(set(
        _bounded_int(value)
        for value in audit.get("compound_blocks", [])
        if _bounded_int(value)
    ))
    return rank, -failed, -conflicts, -compound


def publication_receipt_integrity(
    reply: str,
    audit: dict | None,
    coverage: dict | None = None,
    expected_frozen_binding: dict | None = None,
    expected_generation_purpose: str | None = None,
    expected_prompt_binding: dict | None = None,
) -> dict:
    """Verify that all available receipts belong to the exact publication.

    Legacy handcrafted audits without hashes remain compatible. Live Project L
    receipts carry hashes and must agree. Any declared hash mismatch is a hard
    integrity failure.
    """
    audit = dict(audit or {})
    coverage = dict(coverage or {}) if coverage is not None else None
    issues = []

    declared_reply = str(audit.get("reply_sha256") or "").strip()
    if declared_reply:
        actual_reply = sha256(str(reply or "").encode()).hexdigest()
        if declared_reply != actual_reply:
            issues.append("reply_hash_mismatch")

    publication_draft = str(audit.get("draft_sha256") or "").strip()
    if coverage is not None:
        coverage_draft = str(coverage.get("draft_sha256") or "").strip()
        if publication_draft and coverage_draft and publication_draft != coverage_draft:
            issues.append("coverage_draft_mismatch")

    support = audit.get("claim_support")
    if isinstance(support, dict):
        support_draft = str(support.get("draft_sha256") or "").strip()
        support_citation_draft = str(
            support.get("citation_audit_draft_sha256") or ""
        ).strip()
        support_publication_draft = str(
            support.get("publication_draft_sha256") or ""
        ).strip()
        if (
            support_draft
            and support_citation_draft
            and support_draft != support_citation_draft
        ):
            issues.append("claim_support_source_draft_mismatch")
        if (
            publication_draft
            and support_publication_draft
            and publication_draft != support_publication_draft
        ):
            issues.append("claim_support_publication_draft_mismatch")

    generation = audit.get("generation")
    if isinstance(generation, dict):
        generation_request = str(generation.get("request_sha256") or "").strip()
        generation_output = str(generation.get("content_sha256") or "").strip()
        generation_purpose = str(generation.get("purpose") or "").strip()
        generation_request_integrity = str(
            generation.get("request_integrity") or ""
        ).strip()
        if len(generation_request) != 64:
            issues.append("generation_request_receipt_invalid")
        if len(generation_output) != 64:
            issues.append("generation_output_receipt_invalid")
        if (
            isinstance(support, dict)
            and support_draft
            and generation_output
            and support_draft != generation_output
        ):
            issues.append("generation_claim_support_draft_mismatch")
        if (
            expected_generation_purpose
            and generation_purpose != expected_generation_purpose
        ):
            issues.append("generation_purpose_mismatch")
        if (
            expected_generation_purpose
            and generation_request_integrity != "verified"
        ):
            issues.append("generation_request_not_verified")

        if expected_prompt_binding is not None:
            generation_binding = generation.get("context_binding")
            if not isinstance(generation_binding, dict):
                issues.append("generation_prompt_binding_missing")
            else:
                expected_binding_sha = str(
                    expected_prompt_binding.get("binding_sha256") or ""
                )
                generation_binding_sha = str(
                    generation_binding.get("binding_sha256") or ""
                )
                expected_payload = dict(expected_prompt_binding)
                expected_payload.pop("binding_sha256", None)
                generation_payload = dict(generation_binding)
                generation_payload.pop("binding_sha256", None)
                if (
                    not expected_prompt_binding.get("valid")
                    or str(expected_prompt_binding.get("status") or "") != "verified"
                    or expected_binding_sha != _canonical_sha256(expected_payload)
                ):
                    issues.append("expected_prompt_binding_invalid")
                if generation_binding_sha != _canonical_sha256(generation_payload):
                    issues.append("generation_prompt_binding_receipt_invalid")
                if generation_binding_sha != expected_binding_sha:
                    issues.append("generation_prompt_binding_mismatch")
                if str(generation_binding.get("status") or "") != "verified":
                    issues.append("generation_prompt_binding_unverified")

            transport = generation.get("provider_transport")
            if not isinstance(transport, dict) or not transport:
                issues.append("generation_provider_transport_missing")
            else:
                transport_payload = dict(transport)
                transport_receipt_sha = str(
                    transport_payload.pop("receipt_sha256", "") or ""
                )
                if transport_receipt_sha != _canonical_sha256(transport_payload):
                    issues.append("generation_provider_transport_receipt_invalid")
                if str(transport.get("integrity") or "") != "verified":
                    issues.append("generation_provider_transport_unverified")
                if transport.get("issues"):
                    issues.append("generation_provider_transport_has_issues")
                if str(transport.get("request_sha256") or "") != generation_request:
                    issues.append("generation_provider_transport_request_mismatch")
                if len(str(transport.get("payload_sha256") or "")) != 64:
                    issues.append("generation_provider_payload_hash_invalid")
                if str(transport.get("api") or "") not in {
                    "responses",
                    "chat_completions",
                }:
                    issues.append("generation_provider_api_invalid")
                generation_model = str(generation.get("model_id") or "")
                transport_model = str(transport.get("model_id") or "")
                if not transport_model:
                    issues.append("generation_provider_requested_model_missing")

            provider_response = generation.get("provider_response")
            if not isinstance(provider_response, dict) or not provider_response:
                issues.append("generation_provider_response_missing")
            else:
                response_payload = dict(provider_response)
                response_receipt_sha = str(
                    response_payload.pop("receipt_sha256", "") or ""
                )
                if response_receipt_sha != _canonical_sha256(response_payload):
                    issues.append("generation_provider_response_receipt_invalid")
                if str(provider_response.get("integrity") or "") != "verified":
                    issues.append("generation_provider_response_unverified")
                if provider_response.get("issues"):
                    issues.append("generation_provider_response_has_issues")
                if (
                    str(provider_response.get("request_sha256") or "")
                    != generation_request
                ):
                    issues.append("generation_provider_response_request_mismatch")
                if (
                    str(provider_response.get("content_sha256") or "")
                    != generation_output
                ):
                    issues.append("generation_provider_response_content_mismatch")
                if str(provider_response.get("status") or "") != "complete":
                    issues.append("generation_provider_response_status_invalid")
                response_model = str(
                    provider_response.get("returned_model") or ""
                )
                if generation_model and response_model != generation_model:
                    issues.append("generation_provider_response_model_mismatch")
                if isinstance(transport, dict) and transport:
                    if (
                        str(provider_response.get("transport_receipt_sha256") or "")
                        != str(transport.get("receipt_sha256") or "")
                    ):
                        issues.append("generation_provider_response_transport_mismatch")
                    if (
                        str(provider_response.get("api") or "")
                        != str(transport.get("api") or "")
                    ):
                        issues.append("generation_provider_response_api_mismatch")
                    if (
                        str(provider_response.get("requested_model") or "")
                        != str(transport.get("model_id") or "")
                    ):
                        issues.append(
                            "generation_provider_response_requested_model_mismatch"
                        )
    elif expected_generation_purpose:
        issues.append("generation_receipt_missing")

    expected_binding = (
        dict(expected_frozen_binding or {})
        if isinstance(expected_frozen_binding, dict)
        else None
    )
    coverage_binding = (
        dict((coverage or {}).get("frozen_evidence_binding") or {})
        if isinstance(coverage, dict)
        else {}
    )
    if expected_binding is not None and expected_binding.get("status") != "legacy_unbound":
        if not expected_binding.get("valid"):
            issues.append("expected_frozen_binding_invalid")
        if not coverage_binding:
            issues.append("coverage_frozen_binding_missing")
        else:
            if (
                str(coverage_binding.get("actual_manifest_sha256") or "")
                != str(expected_binding.get("actual_manifest_sha256") or "")
            ):
                issues.append("coverage_manifest_binding_mismatch")
            if (
                str(coverage_binding.get("actual_evidence_packet_sha256") or "")
                != str(expected_binding.get("actual_evidence_packet_sha256") or "")
            ):
                issues.append("coverage_evidence_binding_mismatch")
            if (
                str(expected_binding.get("request_query_sha256") or "")
                and str(coverage_binding.get("request_query_sha256") or "")
                != str(expected_binding.get("request_query_sha256") or "")
            ):
                issues.append("coverage_query_binding_mismatch")

    return {
        "version": "2.0",
        "valid": not issues,
        "issues": issues,
    }


def choose_publication_repair(
    first_reply: str,
    first_audit: dict,
    repaired_reply: str,
    repaired_audit: dict,
    *,
    first_coverage: dict | None = None,
    repaired_coverage: dict | None = None,
    frozen_binding: dict | None = None,
    prompt_binding: dict | None = None,
) -> tuple[str, dict]:
    """Keep a Layer 67 repair only when governed quality improves safely.

    Layer 68 remains the default behaviour when no coverage receipts are supplied.
    With Layers 69–83 receipts, citation quality, quote-bound structural
    coverage and bounded claim-support/consistency quality must not regress;
    at least one governed dimension must strictly improve.
    """
    baseline = dict(first_audit or {})
    candidate = dict(repaired_audit or {})
    first_quality = publication_quality(baseline)
    repair_quality = publication_quality(candidate)
    has_coverage = first_coverage is not None or repaired_coverage is not None
    first_coverage_quality = coverage_quality(first_coverage) if has_coverage else None
    repair_coverage_quality = coverage_quality(repaired_coverage) if has_coverage else None
    first_support_quality = claim_support_quality(baseline.get("claim_support"))
    repair_support_quality = claim_support_quality(candidate.get("claim_support"))
    has_support = first_support_quality is not None or repair_support_quality is not None
    has_generation_receipt = (
        isinstance(baseline.get("generation"), dict)
        or isinstance(candidate.get("generation"), dict)
    )
    first_integrity = publication_receipt_integrity(
        first_reply,
        baseline,
        first_coverage,
        expected_frozen_binding=frozen_binding,
        expected_generation_purpose=(
            "l_user_response"
            if frozen_binding is not None and has_generation_receipt
            else None
        ),
        expected_prompt_binding=(
            prompt_binding if has_generation_receipt else None
        ),
    )
    repair_integrity = publication_receipt_integrity(
        repaired_reply,
        candidate,
        repaired_coverage,
        expected_frozen_binding=frozen_binding,
        expected_generation_purpose=(
            "l_deep_recall_publication_repair"
            if frozen_binding is not None and has_generation_receipt
            else None
        ),
        expected_prompt_binding=(
            prompt_binding if has_generation_receipt else None
        ),
    )

    if first_coverage is not None:
        baseline["coverage"] = dict(first_coverage)
    if repaired_coverage is not None:
        candidate["coverage"] = dict(repaired_coverage)

    metadata = {
        "repair_attempted": True,
        "repair_candidate_status": candidate.get("status"),
        "repair_candidate_quality": list(repair_quality),
        "first_pass_status": baseline.get("status"),
        "first_pass_quality": list(first_quality),
    }
    if has_coverage:
        metadata.update(
            repair_candidate_coverage_quality=list(repair_coverage_quality),
            first_pass_coverage_quality=list(first_coverage_quality),
        )
    if has_support:
        metadata.update(
            repair_candidate_support_quality=(
                list(repair_support_quality)
                if repair_support_quality is not None else None
            ),
            first_pass_support_quality=(
                list(first_support_quality)
                if first_support_quality is not None else None
            ),
        )
    metadata.update(
        first_pass_receipt_integrity=first_integrity,
        repair_candidate_receipt_integrity=repair_integrity,
    )

    if not first_integrity["valid"]:
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="first_pass_receipt_mismatch",
        )
        return first_reply, baseline

    if not repair_integrity["valid"]:
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="repair_receipt_mismatch",
        )
        return first_reply, baseline

    if not str(repaired_reply or "").strip():
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="empty_repair",
        )
        return first_reply, baseline

    if repair_quality < first_quality:
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="citation_quality_regressed",
        )
        return first_reply, baseline
    if has_coverage and repair_coverage_quality < first_coverage_quality:
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="coverage_regressed",
        )
        return first_reply, baseline

    if has_support:
        # A missing semantic receipt on one side is lower confidence than a
        # successfully evaluated receipt. Preserve the safer first pass.
        if first_support_quality is not None and repair_support_quality is None:
            baseline.update(metadata)
            baseline.update(
                repair_accepted=False,
                repair_rejection_reason="claim_support_missing_on_repair",
            )
            return first_reply, baseline
        if (
            first_support_quality is not None
            and repair_support_quality is not None
            and repair_support_quality < first_support_quality
        ):
            baseline.update(metadata)
            baseline.update(
                repair_accepted=False,
                repair_rejection_reason="claim_support_regressed",
            )
            return first_reply, baseline

    citation_improved = repair_quality > first_quality
    coverage_improved = (
        has_coverage and repair_coverage_quality > first_coverage_quality
    )
    support_improved = (
        has_support
        and first_support_quality is not None
        and repair_support_quality is not None
        and repair_support_quality > first_support_quality
    )
    support_added = (
        has_support
        and first_support_quality is None
        and repair_support_quality is not None
    )

    if not (citation_improved or coverage_improved or support_improved or support_added):
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="quality_not_improved",
        )
        return first_reply, baseline

    candidate.update(metadata)
    candidate.update(
        repair_accepted=True,
        repair_acceptance_reason=(
            "audited_quality_coverage_and_claim_support_nonregression"
            if has_support and has_coverage
            else "audited_quality_and_claim_support_nonregression"
            if has_support
            else "audited_quality_and_coverage_nonregression"
            if has_coverage
            else "audited_quality_improved"
        ),
    )
    return repaired_reply, candidate

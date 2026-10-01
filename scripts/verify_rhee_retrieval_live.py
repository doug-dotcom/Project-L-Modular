"""Production pre-deploy smoke for Project L's layered Rhee retrieval stack.

The smoke exercises the real Rhee context packet against live Supabase while
capturing all internal stdout. Deployment logs receive only aggregate receipt
metadata: never memory text, record identifiers, queries or owner identifiers.
"""

from __future__ import annotations

import contextlib
import io
import time

from agents.rhee import rhee_v3 as rhee


QUERY = "Recall diving Bali"
TRANSIENT_RETRIEVAL_CODES = frozenset({
    "PGRST002",
    "PGRST003",
    "57014",
    "HTTP_TIMEOUT",
})
MAX_TRANSIENT_REPLAYS = 1
MAX_RETRY_DELAY_SECONDS = 10.0
RHEE_STAGE_LATENCY_PROFILE_VERSION = "rhee-stage-latency-v2"


def _fail(reason: str) -> None:
    raise SystemExit(f"Project L Rhee retrieval smoke: FAIL {reason}")


def _capture_packet() -> dict:
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink):
            packet = rhee.build_context_packet(QUERY)
    except Exception as exc:
        _fail(type(exc).__name__.lower()[:80] or "unexpected-error")
    if not isinstance(packet, dict):
        _fail("packet-invalid")
    return packet


def _plan(packet: dict) -> dict:
    value = packet.get("recall_plan")
    return value if isinstance(value, dict) else {}


def _transient_retry_delay(plan: dict) -> float | None:
    code = str(plan.get("retrieval_error_code") or "").strip().upper()
    if code not in TRANSIENT_RETRIEVAL_CODES:
        return None

    delays = []
    for candidate in (
        plan.get("retrieval_retry_after"),
        rhee.recall_rpc_retry_after(),
    ):
        try:
            value = float(candidate)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            delays.append(value)

    delay = max(delays) if delays else 1.0
    return min(max(delay, 1.0), MAX_RETRY_DELAY_SECONDS) + 0.25


def _packet_with_bounded_transient_replay() -> tuple[dict, int]:
    packet = _capture_packet()
    plan = _plan(packet)
    if plan.get("retrieval_status") == "checked":
        return packet, 0

    replays = 0
    while replays < MAX_TRANSIENT_REPLAYS:
        delay = _transient_retry_delay(plan)
        if delay is None:
            break
        time.sleep(delay)
        replays += 1
        packet = _capture_packet()
        plan = _plan(packet)
        if plan.get("retrieval_status") == "checked":
            break

    return packet, replays


def main() -> None:
    packet, transient_replays = _packet_with_bounded_transient_replay()

    plan = (
        packet.get("recall_plan")
        if isinstance(packet.get("recall_plan"), dict)
        else {}
    )
    independence = (
        packet.get("evidence_independence")
        if isinstance(packet.get("evidence_independence"), dict)
        else {}
    )
    confidence = (
        packet.get("recall_confidence")
        if isinstance(packet.get("recall_confidence"), dict)
        else {}
    )
    evidence = (
        packet.get("evidence")
        if isinstance(packet.get("evidence"), list)
        else []
    )

    if packet.get("engine") != "rhee":
        _fail("engine-invalid")
    if packet.get("version") != "v5.0":
        _fail("version-invalid")
    if packet.get("recall_active") is not True:
        _fail("recall-inactive")
    if packet.get("deep_recall") is not False:
        _fail("unexpected-deep-recall")
    if len(evidence) < 1:
        _fail("evidence-empty")

    governed_evidence = [
        item for item in evidence
        if isinstance(item, dict) and item.get("provenance") == "owner_scoped_v2"
    ]
    if not governed_evidence:
        _fail("governed-evidence-empty")
    if any(item.get("owner_bound") is not True for item in governed_evidence):
        _fail("owner-binding-lost")
    if any(not isinstance(item.get("authority"), dict) for item in governed_evidence):
        _fail("authority-metadata-lost")
    if any(not isinstance(item.get("freshness"), dict) for item in governed_evidence):
        _fail("freshness-metadata-lost")
    if any(
        not str(item.get("authority", {}).get("class") or "").strip()
        for item in governed_evidence
    ):
        _fail("authority-class-empty")
    if any(
        not str(item.get("freshness", {}).get("class") or "").strip()
        for item in governed_evidence
    ):
        _fail("freshness-class-empty")

    if plan.get("retrieval_status") != "checked":
        _fail("retrieval-unavailable")
    if plan.get("retrieval_query_binding") != "server-verified":
        _fail("query-binding-unverified")
    if str(plan.get("retrieval_query_contract_version") or "") != "2":
        _fail("query-contract-invalid")
    if plan.get("storage_absence_verified") is not False:
        _fail("absence-semantics-invalid")
    if plan.get("absence_semantics") != "retrieval_miss_is_not_storage_absence":
        _fail("absence-contract-missing")

    if independence.get("status") != "checked":
        _fail("independence-unchecked")
    if int(independence.get("evidence_items") or 0) < 1:
        _fail("independence-evidence-empty")
    if int(independence.get("independent_lineages") or 0) < 1:
        _fail("independence-lineage-empty")
    if independence.get("confidence_counts_lineages_not_copies") is not True:
        _fail("independence-contract-invalid")
    if int(independence.get("governed_evidence_items") or 0) != len(governed_evidence):
        _fail("governance-receipt-count-mismatch")
    if int(independence.get("owner_bound_governed_items") or 0) != len(governed_evidence):
        _fail("governance-receipt-owner-mismatch")
    if independence.get("governance_metadata_complete") is not True:
        _fail("governance-receipt-incomplete")
    authority_classes = independence.get("authority_classes")
    freshness_classes = independence.get("freshness_classes")
    if not isinstance(authority_classes, dict) or not authority_classes:
        _fail("governance-receipt-authority-empty")
    if not isinstance(freshness_classes, dict) or not freshness_classes:
        _fail("governance-receipt-freshness-empty")
    if "unknown" in authority_classes or "unknown" in freshness_classes:
        _fail("governance-receipt-unknown-class")

    if confidence.get("storage_absence_verified") is not False:
        _fail("confidence-absence-invalid")
    if str(confidence.get("state") or "") not in {
        "sparse_retrieval",
        "partial_coverage",
        "supported_retrieval",
        "conflicted_retrieval",
    }:
        _fail("confidence-state-invalid")

    if str(confidence.get("state") or "") == "conflicted_retrieval":
        if confidence.get("unresolved_conflict") is not True:
            _fail("conflicted-confidence-without-unresolved-state")
        if plan.get("conflict_state") != "unresolved":
            _fail("conflicted-confidence-plan-state-mismatch")
        if plan.get("conflict_state_reviewed") is not True:
            _fail("conflicted-confidence-unreviewed")

    print(
        "Project L Rhee retrieval smoke: PASS "
        f"profile={RHEE_STAGE_LATENCY_PROFILE_VERSION} "
        f"engine={packet.get('engine')} "
        f"version={packet.get('version')} "
        f"evidence={len(evidence)} "
        f"governed={len(governed_evidence)} "
        f"governance_complete={str(independence.get('governance_metadata_complete')).lower()} "
        f"authority_classes={len(authority_classes)} "
        f"freshness_classes={len(freshness_classes)} "
        f"lineages={independence.get('independent_lineages')} "
        f"duplicates={independence.get('duplicate_representations')} "
        f"binding={plan.get('retrieval_query_binding')} "
        f"contract={plan.get('retrieval_query_contract_version')} "
        f"confidence={confidence.get('state')} "
        f"latency_ms={plan.get('latency_ms')} "
        f"packet_latency_ms={plan.get('packet_latency_ms')} "
        f"temporal_latency_ms={plan.get('temporal_latency_ms')} "
        f"slowest_stage={plan.get('slowest_stage')} "
        f"slowest_stage_ms={plan.get('slowest_stage_ms')} "
        f"transient_replays={transient_replays}"
    )


if __name__ == "__main__":
    main()

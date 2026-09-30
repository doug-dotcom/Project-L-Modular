"""Production pre-deploy smoke for Project L's layered Rhee retrieval stack.

The smoke exercises the real Rhee context packet against live Supabase while
capturing all internal stdout. Deployment logs receive only aggregate receipt
metadata: never memory text, record identifiers, queries or owner identifiers.
"""

from __future__ import annotations

import contextlib
import io

from agents.rhee import rhee_v3 as rhee


QUERY = "Recall diving Bali"


def _fail(reason: str) -> None:
    raise SystemExit(f"Project L Rhee retrieval smoke: FAIL {reason}")


def main() -> None:
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink):
            packet = rhee.build_context_packet(QUERY)
    except Exception as exc:
        _fail(type(exc).__name__.lower()[:80] or "unexpected-error")

    if not isinstance(packet, dict):
        _fail("packet-invalid")

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

    if confidence.get("storage_absence_verified") is not False:
        _fail("confidence-absence-invalid")
    if str(confidence.get("state") or "") not in {
        "sparse_retrieval",
        "partial_coverage",
        "supported_retrieval",
    }:
        _fail("confidence-state-invalid")

    print(
        "Project L Rhee retrieval smoke: PASS "
        f"engine={packet.get('engine')} "
        f"version={packet.get('version')} "
        f"evidence={len(evidence)} "
        f"lineages={independence.get('independent_lineages')} "
        f"duplicates={independence.get('duplicate_representations')} "
        f"binding={plan.get('retrieval_query_binding')} "
        f"contract={plan.get('retrieval_query_contract_version')} "
        f"confidence={confidence.get('state')} "
        f"latency_ms={plan.get('latency_ms')}"
    )


if __name__ == "__main__":
    main()

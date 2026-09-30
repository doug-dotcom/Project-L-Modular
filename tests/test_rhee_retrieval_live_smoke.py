import importlib.util
from pathlib import Path


SCRIPT = Path("scripts/verify_rhee_retrieval_live.py")


def load_module():
    spec = importlib.util.spec_from_file_location("verify_rhee_retrieval_live", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def packet():
    return {
        "engine": "rhee",
        "version": "v5.0",
        "recall_active": True,
        "deep_recall": False,
        "evidence": [
            {
                "source": "memory_sport:1",
                "quote_source": "SECRET MEMORY TEXT",
                "provenance": "owner_scoped_v2",
                "owner_bound": True,
                "authority": {
                    "class": "direct_user_promoted_memory",
                    "precedence": 70,
                },
                "freshness": {
                    "class": "non_temporal_memory",
                    "temporalCurrentnessHandledSeparately": True,
                },
            }
        ],
        "evidence_independence": {
            "status": "checked",
            "evidence_items": 1,
            "independent_lineages": 1,
            "shared_lineages": 0,
            "duplicate_representations": 0,
            "confidence_counts_lineages_not_copies": True,
            "governed_evidence_items": 1,
            "owner_bound_governed_items": 1,
            "governance_metadata_complete": True,
            "authority_classes": {"direct_user_promoted_memory": 1},
            "freshness_classes": {"non_temporal_memory": 1},
        },
        "recall_confidence": {
            "state": "sparse_retrieval",
            "confidence": "low_to_moderate",
            "evidence_sources": 1,
            "storage_absence_verified": False,
        },
        "recall_plan": {
            "status": "checked",
            "retrieval_status": "checked",
            "retrieval_query_binding": "server-verified",
            "retrieval_query_contract_version": "2",
            "storage_absence_verified": False,
            "absence_semantics": "retrieval_miss_is_not_storage_absence",
            "latency_ms": 123,
        },
        "context": "SECRET CONTEXT TEXT",
    }


def test_rhee_live_smoke_prints_receipt_not_memory_content(monkeypatch, capsys):
    smoke = load_module()

    def build_context_packet(query):
        assert query == "Recall diving Bali"
        print("INTERNAL SECRET LOG")
        return packet()

    monkeypatch.setattr(smoke.rhee, "build_context_packet", build_context_packet)

    smoke.main()

    output = capsys.readouterr().out
    assert "Project L Rhee retrieval smoke: PASS" in output
    assert "binding=server-verified" in output
    assert "contract=2" in output
    assert "evidence=1" in output
    assert "governed=1" in output
    assert "governance_complete=true" in output
    assert "authority_classes=1" in output
    assert "freshness_classes=1" in output
    assert "lineages=1" in output
    assert "SECRET MEMORY TEXT" not in output
    assert "SECRET CONTEXT TEXT" not in output
    assert "INTERNAL SECRET LOG" not in output
    assert "Recall diving Bali" not in output


def test_rhee_live_smoke_fails_closed_on_unverified_binding(monkeypatch):
    smoke = load_module()
    bad = packet()
    bad["recall_plan"] = {
        **bad["recall_plan"],
        "retrieval_query_binding": "legacy-unverified",
    }
    monkeypatch.setattr(smoke.rhee, "build_context_packet", lambda query: bad)

    try:
        smoke.main()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "query-binding-unverified" in str(exc)


def test_rhee_live_smoke_fails_closed_on_wrong_contract(monkeypatch):
    smoke = load_module()
    bad = packet()
    bad["recall_plan"] = {
        **bad["recall_plan"],
        "retrieval_query_contract_version": "1",
    }
    monkeypatch.setattr(smoke.rhee, "build_context_packet", lambda query: bad)

    try:
        smoke.main()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "query-contract-invalid" in str(exc)



def test_rhee_live_smoke_fails_closed_when_governance_metadata_is_lost(monkeypatch):
    smoke = load_module()
    bad = packet()
    bad["evidence"] = [
        {
            **bad["evidence"][0],
            "authority": None,
        }
    ]
    monkeypatch.setattr(smoke.rhee, "build_context_packet", lambda query: bad)

    try:
        smoke.main()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "authority-metadata-lost" in str(exc)


def test_rhee_live_smoke_fails_closed_when_owner_binding_is_lost(monkeypatch):
    smoke = load_module()
    bad = packet()
    bad["evidence"] = [
        {
            **bad["evidence"][0],
            "owner_bound": False,
        }
    ]
    monkeypatch.setattr(smoke.rhee, "build_context_packet", lambda query: bad)

    try:
        smoke.main()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "owner-binding-lost" in str(exc)



def test_rhee_live_smoke_fails_closed_on_governance_receipt_mismatch(monkeypatch):
    smoke = load_module()
    bad = packet()
    bad["evidence_independence"] = {
        **bad["evidence_independence"],
        "governed_evidence_items": 0,
    }
    monkeypatch.setattr(smoke.rhee, "build_context_packet", lambda query: bad)

    try:
        smoke.main()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "governance-receipt-count-mismatch" in str(exc)

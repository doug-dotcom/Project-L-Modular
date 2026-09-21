import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from core.cognition.publication_repair import sealed_reply_persistence_receipt
from core.cognition.working_memory import ActiveContextService
from memory.continuity.live_short_term import write_short_term_memory


NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def h(text):
    return sha256(str(text).encode("utf-8")).hexdigest()


class FakeResponse:
    def __init__(self, data):
        self.data = data


class EchoQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        self.client.writes.append((self.table_name, dict(self.payload)))
        return FakeResponse([{"id": len(self.client.writes), **self.payload}])


class EchoSupabase:
    def __init__(self):
        self.writes = []

    def table(self, table_name):
        return EchoQuery(self, table_name)


def publication_seal(reply):
    return {
        "status": "sealed",
        "valid": True,
        "final_reply_sha256": h(reply),
    }


def verified_short_term(reply):
    return {
        "saved": True,
        "table": "short_term_general",
        "role": "assistant",
        "id": 1,
        "content_sha256": h(reply),
        "stored_content_sha256": h(reply),
        "integrity": "verified",
    }


def verified_working_memory(reply):
    return {
        "engine": "cognitive_working_memory",
        "last_reply_sha256": h(reply),
        "last_reply_size": len(reply),
    }


def raw_row(reply):
    return {
        "id": 1,
        "role": "assistant",
        "source": "chat",
        "content": reply,
    }


def test_layer85_short_term_preserves_exact_reply_text_including_whitespace():
    client = EchoSupabase()
    reply = "  exact final reply\n"

    result = write_short_term_memory(
        client,
        "short_term_general",
        "assistant",
        reply,
    )

    assert client.writes == [
        (
            "short_term_general",
            {"role": "assistant", "content": reply},
        )
    ]
    assert result["integrity"] == "verified"
    assert result["content_sha256"] == h(reply)
    assert result["stored_content_sha256"] == h(reply)


def test_layer85_working_memory_records_hash_not_reply_content():
    service = ActiveContextService()
    service.begin_turn(
        "doug",
        "Go",
        {"problem_type": "execution"},
        {},
        {},
        now=NOW,
    )
    reply = "Sensitive sealed reply"

    completed = service.complete_turn(
        "doug",
        reply,
        now=NOW,
    )

    assert completed["last_reply_sha256"] == h(reply)
    assert completed["last_reply_size"] == len(reply)
    assert reply not in json.dumps(completed)


def test_layer85_all_three_persistence_targets_verify_against_sealed_reply():
    reply = "Sealed answer"

    receipt = sealed_reply_persistence_receipt(
        reply,
        publication_seal(reply),
        verified_working_memory(reply),
        verified_short_term(reply),
        raw_row(reply),
    )

    assert receipt["status"] == "verified"
    assert receipt["valid"] is True
    assert receipt["trusted_for_recall"] is True
    assert receipt["issues"] == []
    assert receipt["degraded"] == []
    assert receipt["final_reply_sha256"] == h(reply)
    assert len(receipt["receipt_sha256"]) == 64


def test_layer85_memory_outage_degrades_without_invalidating_the_reply():
    reply = "Sealed answer"
    short_term = {
        "saved": False,
        "reason": "supabase_unavailable",
    }

    receipt = sealed_reply_persistence_receipt(
        reply,
        publication_seal(reply),
        verified_working_memory(reply),
        short_term,
        None,
    )

    assert receipt["status"] == "degraded"
    assert receipt["valid"] is True
    assert receipt["trusted_for_recall"] is False
    assert "short_term_not_saved:supabase_unavailable" in receipt["degraded"]
    assert "raw_catchall_not_saved" in receipt["degraded"]


def test_layer85_short_term_claimed_success_with_wrong_hash_is_mismatch():
    reply = "Sealed answer"
    short_term = verified_short_term(reply)
    short_term["stored_content_sha256"] = h("different")
    short_term["integrity"] = "mismatch"

    receipt = sealed_reply_persistence_receipt(
        reply,
        publication_seal(reply),
        verified_working_memory(reply),
        short_term,
        raw_row(reply),
    )

    assert receipt["status"] == "mismatch"
    assert receipt["valid"] is False
    assert receipt["trusted_for_recall"] is False
    assert "short_term_storage_hash_mismatch" in receipt["issues"]
    assert "short_term_stored_hash_mismatch" in receipt["issues"]


def test_layer85_raw_catchall_content_mismatch_is_detected():
    reply = "Sealed answer"
    wrong_raw = raw_row("different answer")

    receipt = sealed_reply_persistence_receipt(
        reply,
        publication_seal(reply),
        verified_working_memory(reply),
        verified_short_term(reply),
        wrong_raw,
    )

    assert receipt["status"] == "mismatch"
    assert "raw_catchall_content_hash_mismatch" in receipt["issues"]


def test_layer85_raw_row_without_echo_is_degraded_not_falsely_mismatched():
    reply = "Sealed answer"

    receipt = sealed_reply_persistence_receipt(
        reply,
        publication_seal(reply),
        verified_working_memory(reply),
        verified_short_term(reply),
        {"id": 10},
    )

    assert receipt["status"] == "degraded"
    assert receipt["valid"] is True
    assert "raw_catchall_storage_unverified" in receipt["degraded"]
    assert "raw_catchall_role_unverified" in receipt["degraded"]


def test_layer85_seal_hash_mismatch_is_integrity_failure():
    reply = "Sealed answer"
    bad_seal = publication_seal("different answer")

    receipt = sealed_reply_persistence_receipt(
        reply,
        bad_seal,
        verified_working_memory(reply),
        verified_short_term(reply),
        raw_row(reply),
    )

    assert receipt["status"] == "mismatch"
    assert "persistence_final_seal_hash_mismatch" in receipt["issues"]


def test_layer85_persistence_receipt_contains_hashes_not_reply_text():
    reply = "PRIVATE SEALED ASSISTANT RESPONSE"

    receipt = sealed_reply_persistence_receipt(
        reply,
        publication_seal(reply),
        verified_working_memory(reply),
        verified_short_term(reply),
        raw_row(reply),
    )
    encoded = json.dumps(receipt)

    assert reply not in encoded
    assert h(reply) in encoded


def test_layer85_live_server_builds_persistence_receipt_after_all_three_targets():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    working_idx = source.index(
        'cognitive_packet["working_memory"] = active_context_service.complete_turn('
    )
    short_idx = source.index("short_term_assistant = write_live_short_term(")
    raw_idx = source.index("raw_assistant_row = write_raw_catchall(")
    receipt_idx = source.index(
        "assistant_persistence = sealed_reply_persistence_receipt("
    )
    payload_idx = source.index(
        '"assistant_persistence": cognitive_packet.get("assistant_persistence", {})'
    )

    assert working_idx < short_idx < raw_idx < receipt_idx < payload_idx
    assert 'cognitive_packet["assistant_persistence"] = assistant_persistence' in source
    assert '"assistant_integrity": short_term_assistant.get("integrity")' in source


def test_layer85_evaluation_manifest_exposes_persistence_binding():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "evidence_evaluation.py"
    ).read_text(encoding="utf-8")

    assert '"sealed_reply_persistence_binding"' in source

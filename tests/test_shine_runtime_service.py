import hashlib
import hmac
import json

import pytest

from services import shine_runtime_service as runtime
from services import shine_trust_storage as trust_storage


@pytest.fixture(autouse=True)
def trust_storage_env(monkeypatch):
    monkeypatch.setenv(
        "SHINE_AI_TRUST_STATE_STORAGE_KEYRING_JSON",
        json.dumps({
            "storage-a": "S" * 48,
            "storage-b": "T" * 48,
        }),
    )
    monkeypatch.setenv(
        "SHINE_AI_TRUST_STATE_STORAGE_ACTIVE_KEY_ID",
        "storage-a",
    )


def test_shine_ai_signature_matches_keyring_contract(monkeypatch):
    monkeypatch.setenv("SHINE_AI_APP_ID", "shine-me")
    monkeypatch.setenv("SHINE_AI_APP_KEY_ID", "runtime-1")
    monkeypatch.setenv("SHINE_AI_APP_SECRET", "s" * 48)
    body = json.dumps({"app": "shine-me", "task": "route"}).encode()

    headers = runtime._shine_ai_headers(body, now=1_800_000_000, nonce="n" * 16)

    signed = b"\n".join([
        b"shine-me",
        b"runtime-1",
        b"1800000000",
        b"nnnnnnnnnnnnnnnn",
        b"POST",
        b"/v1/respond",
        body,
    ])
    expected = hmac.new(b"s" * 48, signed, hashlib.sha256).hexdigest()
    assert headers["X-Shine-Signature"] == expected
    assert headers["X-Shine-Key-Id"] == "runtime-1"


def test_concierge_write_mode_stays_with_l_action_journal():
    snapshot = runtime._concierge_snapshot({
        "requestId": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "route": {
            "resolverVersion": "test",
            "mode": "do",
            "selectedRoutes": [{
                "specialistKey": "calendar",
                "capability": "calendar_package",
                "role": "source",
            }],
        },
        "foundation": {"requiresFoundationBridge": False},
    })

    assert snapshot["dispatch_allowed"] is False
    assert snapshot["execution_owner"] == "l-durable-action-router"


def test_concierge_read_mode_can_dispatch_after_durable_commit():
    snapshot = runtime._concierge_snapshot({
        "requestId": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "route": {
            "resolverVersion": "test",
            "mode": "explore",
            "selectedRoutes": [{
                "specialistKey": "travel",
                "capability": "trip_planning",
                "role": "source",
            }],
        },
        "foundation": {"requiresFoundationBridge": True},
    })

    assert snapshot["dispatch_allowed"] is True
    assert snapshot["execution_owner"] == "concierge-read"


def test_concierge_results_become_one_l_capability_packet():
    route = runtime.concierge_route_packet({
        "status": "completed",
        "results": [{
            "specialist": "travel",
            "summary": "A specialist result.",
            "authoritative": True,
        }],
        "tasks": [],
    })

    assert route["handled"] is True
    assert route["capability"] == "shine_concierge"
    assert route["status"] == "ok"
    assert route["reply"] == "A specialist result."


def test_preflight_keeps_component_failures_fail_soft(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "_foundation_snapshot",
        lambda db, user_id: {"status": "healthy", "specialists": []},
    )

    calls = []
    def fake_edge(slug, **kwargs):
        calls.append(slug)
        if slug == "concierge-intake":
            return {
                "requestId": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
                "route": {
                    "mode": "ask",
                    "selectedRoutes": [],
                    "resolverVersion": "test",
                },
                "foundation": {"requiresFoundationBridge": False},
            }
        raise RuntimeError("defence unavailable")

    monkeypatch.setattr(runtime, "_edge_post", fake_edge)
    monkeypatch.setattr(
        runtime,
        "_shine_ai_advisory",
        lambda **kwargs: {"status": "unavailable", "reason_code": "test"},
    )

    receipt = runtime.preflight_shine_request(
        object(),
        user_id="4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        authorization="Bearer token",
        message="hello",
        request_id="4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
    )

    assert receipt["status"] == "degraded"
    assert receipt["components"]["l"]["status"] == "active"
    assert receipt["components"]["concierge"]["status"] == "planned"
    assert receipt["components"]["defence"]["status"] == "unavailable"
    assert receipt["components"]["shine_ai"]["status"] == "unavailable"
    assert calls == ["concierge-intake", "defence-companion"]



def test_runtime_trace_is_content_free_and_carries_shine_ai_attestation():
    digest = "a" * 64
    runtime_packet = {
        "version": runtime.RUNTIME_VERSION,
        "request_id": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "status": "ready",
        "warnings": [],
        "components": {
            "l": {
                "status": "active",
                "authority": "voice+synthesis+durable-task",
                "runtime": {
                    "provider": "railway",
                    "commit": "commit-1",
                    "branch": "main",
                    "deployment": "deploy-1",
                    "service": "Project-L-Modular",
                    "environment": "production",
                },
            },
            "foundation": {
                "status": "healthy",
                "specialist_count": 1,
                "executable_count": 1,
                "blocked_count": 0,
                "specialists": [{
                    "app_id": "shine-travel",
                    "capability_id": "trip_planning",
                    "executable": True,
                    "runtime_available": True,
                }],
            },
            "concierge": {
                "status": "planned",
                "request_id": "c5cce6c2-d07a-46bb-84c6-07b1bd8ec892",
                "resolver_version": "v1",
                "mode": "explore",
                "dispatch_allowed": True,
                "execution_owner": "concierge-read",
                "selected_routes": [{
                    "specialistKey": "travel",
                    "capability": "trip_planning",
                    "role": "source",
                }],
                "foundation_routes": ["trip_planning"],
            },
            "defence": {
                "status": "completed",
                "summary": "PRIVATE DEFENCE SUMMARY",
                "reviews": [{
                    "appId": "project-l",
                    "reviewCommitSha": "abc123",
                    "profileVersion": "1",
                    "status": "reviewed",
                    "limitation": "PRIVATE DEFENCE LIMITATION",
                }],
                "boundaries": {"snapshotOnly": True},
            },
            "shine_ai": {
                "status": "ok",
                "answer": "PRIVATE ADVISORY TEXT MUST NOT ENTER TRACE",
                "route": "model",
                "provider": "openai",
                "model": "example-model",
                "model_tier": "fast",
                "reason": "PRIVATE ROUTING REASON",
                "request_id": "ai-request-1",
                "decision_trace": {
                    "version": 1,
                    "algorithm": "sha256",
                    "scope": "control-plane",
                    "service_version": "1.37.0",
                    "service_release": "layer-137",
                    "planning_sha256": digest,
                    "recovery_sha256": digest,
                    "execution_sha256": digest,
                    "grounding_sha256": digest,
                    "verification_sha256": digest,
                    "delivery_sha256": digest,
                    "lineage_sha256": digest,
                },
            },
        },
    }
    execution = {
        "status": "completed",
        "request_id": "c5cce6c2-d07a-46bb-84c6-07b1bd8ec892",
        "tasks": [{
            "id": "task-1",
            "specialist_key": "travel",
            "status": "completed",
            "action_type": "read",
            "result_summary": "PRIVATE TASK SUMMARY",
        }],
        "results": [{
            "specialist": "travel",
            "result_type": "trip_plan",
            "summary": "PRIVATE SPECIALIST RESULT",
            "payload": {"secret": "PRIVATE PAYLOAD"},
            "authoritative": True,
        }],
    }

    trace = runtime.build_runtime_trace(runtime_packet, execution)
    rendered = json.dumps(trace, sort_keys=True)

    assert trace["version"] == runtime.RUNTIME_TRACE_VERSION
    assert trace["content_exposed"] is False
    assert trace["components"]["shine_ai"]["decision_lineage_sha256"] == digest
    assert trace["component_status"]["l"] == "active"
    assert "PRIVATE ADVISORY" not in rendered
    assert "PRIVATE TASK SUMMARY" not in rendered
    assert "PRIVATE SPECIALIST RESULT" not in rendered
    assert "PRIVATE PAYLOAD" not in rendered
    assert "PRIVATE DEFENCE SUMMARY" not in rendered
    assert "PRIVATE DEFENCE LIMITATION" not in rendered
    assert "PRIVATE ROUTING REASON" not in rendered


def test_runtime_trace_ignores_private_text_but_changes_on_control_plane_drift():
    base = {
        "version": runtime.RUNTIME_VERSION,
        "request_id": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "status": "ready",
        "warnings": [],
        "components": {
            "l": {"status": "active", "authority": "voice+synthesis+durable-task"},
            "foundation": {"status": "healthy", "specialists": []},
            "concierge": {
                "status": "planned",
                "mode": "ask",
                "dispatch_allowed": False,
                "execution_owner": "l-core",
                "selected_routes": [],
            },
            "defence": {"status": "completed", "summary": "one", "reviews": []},
            "shine_ai": {
                "status": "ok",
                "answer": "first private answer",
                "route": "model",
                "model_tier": "fast",
            },
        },
    }
    first = runtime.build_runtime_trace(base)

    changed_text = json.loads(json.dumps(base))
    changed_text["components"]["shine_ai"]["answer"] = "second private answer"
    assert runtime.build_runtime_trace(changed_text)["lineage_sha256"] == first["lineage_sha256"]

    changed_control = json.loads(json.dumps(base))
    changed_control["components"]["concierge"]["mode"] = "explore"
    assert runtime.build_runtime_trace(changed_control)["lineage_sha256"] != first["lineage_sha256"]



def runtime_for_human_status(verification_status="verified"):
    return {
        "version": runtime.RUNTIME_VERSION,
        "request_id": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "status": "ready",
        "warnings": [],
        "components": {
            "l": {"status": "active", "authority": "voice+synthesis+durable-task"},
            "foundation": {"status": "healthy", "specialists": []},
            "concierge": {
                "status": "planned",
                "mode": "ask",
                "dispatch_allowed": False,
                "execution_owner": "l-core",
                "selected_routes": [],
            },
            "defence": {"status": "completed", "reviews": []},
            "shine_ai": {
                "status": "ok",
                "decision_trace_verification": {
                    "version": "shine-ai/decision-trace-verification-v1",
                    "status": verification_status,
                    "verified": verification_status == "verified",
                    "lineage_sha256": "a" * 64,
                },
                "decision_trace_authenticity": {
                    "version": "shine-ai/decision-trace-authenticity-v1",
                    "status": "authenticated",
                    "authenticated": True,
                    "key_id": "trace-v1",
                    "public_key_sha256": "b" * 64,
                    "keyset_sha256": "c" * 64,
                    "lineage_sha256": "a" * 64,
                },
            },
        },
    }


def test_human_status_hides_backend_detail_on_clean_completion():
    status = runtime.build_human_status(
        runtime_for_human_status(),
        {"status": "not_required", "tasks": [], "results": []},
        final=True,
    )

    assert status["state"] == "complete"
    assert status["can_continue"] is True
    assert status["needs_user_action"] is False
    assert status["issue_count"] == 0
    assert "components" not in status


def test_human_status_reports_degraded_without_exposing_component_names():
    packet = runtime_for_human_status("invalid")
    status = runtime.build_human_status(
        packet,
        {"status": "not_required", "tasks": [], "results": []},
        final=True,
    )

    assert status["state"] == "degraded"
    assert status["can_continue"] is True
    assert status["needs_user_action"] is False
    assert status["issue_count"] == 1
    assert "shine_ai" not in json.dumps(status)


def test_human_status_marks_real_user_action_required():
    status = runtime.build_human_status(
        runtime_for_human_status(),
        {
            "status": "pending",
            "tasks": [{
                "id": "task-1",
                "specialist_key": "calendar",
                "status": "consent_required",
                "action_type": "write",
            }],
            "results": [],
        },
        final=True,
    )

    assert status["state"] == "action-required"
    assert status["can_continue"] is False
    assert status["needs_user_action"] is True


def test_pending_specialist_is_degraded_not_complete_and_never_replayed():
    packet = runtime_for_human_status()
    execution = {
        "status": "pending",
        "observation_poll_count": 9,
        "observation_timed_out": True,
        "tasks": [{
            "id": "task-1",
            "specialist_key": "travel",
            "status": "running",
            "action_type": "read",
        }],
        "results": [],
    }

    recovery = runtime.build_runtime_recovery(packet, execution, final=True)
    status = runtime.build_human_status(packet, execution, final=True)

    assert recovery["mode"] == "partial"
    assert recovery["stage"] == "specialist-execution"
    assert recovery["observation_poll_count"] == 9
    assert recovery["observation_timed_out"] is True
    assert recovery["automatic_retry_count"] == 0
    assert recovery["write_replay_allowed"] is False
    assert recovery["paid_model_retry_allowed"] is False
    assert recovery["read_only_observation_allowed"] is True
    assert status["state"] == "degraded"
    assert status["recovery"]["state"] == "partial"
    assert status["recovery"]["write_replay_allowed"] is False
    assert status["recovery"]["paid_model_retry_allowed"] is False


def test_shine_ai_memory_degradation_becomes_one_safe_recovery_state():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["recovery"] = {
        "version": 1,
        "mode": "degraded",
        "failure_stage": "memory",
        "action": "context-only-model",
        "automatic_retry_count": 0,
    }

    recovery = runtime.build_runtime_recovery(packet, {"status": "not_required"}, final=True)
    status = runtime.build_human_status(packet, {"status": "not_required"}, final=True)

    assert recovery["mode"] == "degraded"
    assert recovery["stage"] == "memory"
    assert recovery["can_continue"] is True
    assert recovery["next_step"] == "continue"
    assert status["state"] == "degraded"
    assert status["can_continue"] is True
    assert "shine_ai" not in json.dumps(status)


def test_invalid_attestation_is_classified_as_recovery_degradation():
    packet = runtime_for_human_status("invalid")

    recovery = runtime.build_runtime_recovery(packet, {"status": "not_required"}, final=True)
    status = runtime.build_human_status(packet, {"status": "not_required"}, final=True)

    assert recovery["mode"] == "degraded"
    assert recovery["stage"] == "attestation"
    assert "attestation-degraded" in recovery["reason_codes"]
    assert status["state"] == "degraded"
    assert status["recovery"]["state"] == "degraded"


def test_user_action_recovery_never_authorises_write_replay():
    packet = runtime_for_human_status()
    execution = {
        "status": "pending",
        "tasks": [{
            "id": "task-1",
            "specialist_key": "calendar",
            "status": "consent_required",
            "action_type": "write",
        }],
        "results": [],
    }

    recovery = runtime.build_runtime_recovery(packet, execution, final=True)
    status = runtime.build_human_status(packet, execution, final=True)

    assert recovery["mode"] == "user-action"
    assert recovery["needs_user_action"] is True
    assert recovery["can_continue"] is False
    assert recovery["next_step"] == "user-action"
    assert recovery["write_replay_allowed"] is False
    assert recovery["paid_model_retry_allowed"] is False
    assert status["state"] == "action-required"
    assert status["recovery"]["write_replay_allowed"] is False


def test_runtime_trace_binds_recovery_control_plane_without_private_content():
    base = runtime_for_human_status()
    base["recovery"] = runtime.build_runtime_recovery(
        base,
        {"status": "not_required"},
        final=True,
    )
    first = runtime.build_runtime_trace(base, {"status": "not_required"})

    changed = json.loads(json.dumps(base))
    changed["recovery"]["mode"] = "degraded"
    changed["recovery"]["stage"] = "memory"
    changed["recovery"]["reason_codes"] = ["PRIVATE-REASON-TEXT-NOT-HASHED"]
    second = runtime.build_runtime_trace(changed, {"status": "not_required"})

    assert first["version"] == "shine/runtime-trace-v8"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-REASON-TEXT-NOT-HASHED" not in json.dumps(second)



TRACE_PUBLIC_KEY_B64 = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
TRACE_PUBLIC_KEY_SHA256 = "56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c"
TRACE_SINGLE_KEYSET_SHA256 = "00d100d5873dd2fecc3049dc501b2f2f5dfc268710858b9cf68b0f5858666f4a"


class FakeTrustResult:
    def __init__(self, data):
        self.data = data


class FakeTrustRedis:
    def __init__(self):
        self.rows = {}

    def hgetall(self, key):
        return dict(self.rows.get(key, {}))

    def eval(self, _script, _numkeys, key, *args):
        (
            expected_generation,
            expected_state_sha,
            expected_keyset_sha,
            next_generation,
            next_state_sha,
            next_keyset_sha,
            checkpoint_json,
        ) = args
        expected_generation = int(expected_generation)
        next_generation = int(next_generation)
        current = self.rows.get(key)

        if current is None:
            if expected_generation != 0:
                return ["missing"]
            self.rows[key] = {
                "generation": str(next_generation),
                "state_sha256": next_state_sha,
                "keyset_sha256": next_keyset_sha,
                "checkpoint_json": checkpoint_json,
            }
            return ["created"]

        current_generation = int(current["generation"])
        if current_generation != expected_generation:
            return ["precondition-generation", str(current_generation)]
        if current["state_sha256"] != expected_state_sha:
            return ["precondition-state", current["state_sha256"]]
        if current["keyset_sha256"] != expected_keyset_sha:
            return ["precondition-keyset", current["keyset_sha256"]]
        if next_generation < current_generation:
            return ["rollback"]
        if next_generation > current_generation + 1:
            return ["generation-skip"]
        if (
            next_generation == current_generation
            and next_keyset_sha != current["keyset_sha256"]
        ):
            return ["equivocation"]

        self.rows[key] = {
            "generation": str(next_generation),
            "state_sha256": next_state_sha,
            "keyset_sha256": next_keyset_sha,
            "checkpoint_json": checkpoint_json,
        }
        return [
            "refreshed"
            if next_generation == current_generation
            else "advanced"
        ]


def seed_checkpoint(redis, keyset):
    state = trust_storage.project_trust_state(keyset)
    checkpoint = trust_storage.create_rollback_checkpoint(state)
    redis.rows[trust_storage.REDIS_CHECKPOINT_KEY] = {
        "generation": str(state["generation"]),
        "state_sha256": checkpoint["stateSha256"],
        "keyset_sha256": checkpoint["keyset_sha256"],
        "checkpoint_json": json.dumps(
            checkpoint,
            separators=(",", ":"),
        ),
    }


class FakeTrustDB:
    def __init__(
        self,
        state=None,
        *,
        inconsistent_reason=None,
        sealed=True,
    ):
        self.state = state
        self.inconsistent_reason = inconsistent_reason
        self.rpc_calls = []
        self.sealed = sealed
        if self.state is not None and sealed:
            self._seal_current()

    def _seal_current(self):
        keyset = self.state["trusted_keyset"]
        envelope = trust_storage.create_authenticated_envelope(keyset)
        self.state["state_sha256"] = envelope["stateSha256"]
        self.state["storage_auth_key_id"] = envelope["authKeyId"]
        self.state["storage_auth_tag"] = envelope["authTag"]
        self.sealed = True

    def _snapshot(self, version):
        if self.inconsistent_reason:
            return FakeTrustResult({
                "status": "inconsistent",
                "reason_code": self.inconsistent_reason,
            })
        if self.state is None:
            return FakeTrustResult({"status": "unbootstrapped"})

        payload = {
            "status": "trusted",
            "generation": self.state["generation"],
            "keyset_sha256": self.state["keyset_sha256"],
            "trusted_keyset": self.state["trusted_keyset"],
            "source": self.state.get("source"),
            "authorization_key_id": self.state.get(
                "authorization_key_id"
            ),
            "authorization_public_key_sha256": self.state.get(
                "authorization_public_key_sha256"
            ),
            "ledger_rows": self.state.get("ledger_rows", 1),
        }
        if version == 3:
            if not self.sealed:
                return FakeTrustResult({
                    **payload,
                    "status": "unsealed",
                    "reason_code": "trust-state-authentication-missing",
                })
            payload.update({
                "state_sha256": self.state["state_sha256"],
                "storage_auth_key_id": self.state[
                    "storage_auth_key_id"
                ],
                "storage_auth_tag": self.state["storage_auth_tag"],
            })
        return FakeTrustResult(payload)

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        db = self

        class Call:
            def execute(self):
                if name == "shine_ai_trace_trust_snapshot_v2":
                    return db._snapshot(2)
                if name == "shine_ai_trace_trust_snapshot_v3":
                    return db._snapshot(3)
                if name == "shine_ai_trace_trust_seal_v3":
                    assert db.state is not None
                    assert (
                        db.state["generation"]
                        == params["p_expected_generation"]
                    )
                    assert (
                        db.state["keyset_sha256"]
                        == params["p_expected_keyset_sha256"]
                    )
                    db.state["state_sha256"] = params["p_state_sha256"]
                    db.state["storage_auth_key_id"] = params[
                        "p_storage_auth_key_id"
                    ]
                    db.state["storage_auth_tag"] = params[
                        "p_storage_auth_tag"
                    ]
                    db.sealed = True
                    return FakeTrustResult({
                        "status": "sealed",
                        "generation": db.state["generation"],
                        "keyset_sha256": db.state["keyset_sha256"],
                    })
                if name == "shine_ai_trace_trust_bootstrap_v3":
                    assert params["p_generation"] == 1
                    db.state = {
                        "generation": 1,
                        "keyset_sha256": params["p_keyset_sha256"],
                        "trusted_keyset": params["p_trusted_keyset"],
                        "source": "genesis-pin",
                        "ledger_rows": 1,
                        "state_sha256": params["p_state_sha256"],
                        "storage_auth_key_id": params[
                            "p_storage_auth_key_id"
                        ],
                        "storage_auth_tag": params[
                            "p_storage_auth_tag"
                        ],
                    }
                    db.sealed = True
                    return FakeTrustResult({
                        "status": "trusted",
                        "generation": 1,
                        "keyset_sha256": params["p_keyset_sha256"],
                    })
                if name == "shine_ai_trace_trust_observe_v3":
                    assert db.state is not None
                    assert (
                        db.state["generation"]
                        == params["p_expected_generation"]
                    )
                    assert (
                        db.state["keyset_sha256"]
                        == params["p_expected_keyset_sha256"]
                    )
                    db.state["trusted_keyset"] = params[
                        "p_trusted_keyset"
                    ]
                    db.state["state_sha256"] = params["p_state_sha256"]
                    db.state["storage_auth_key_id"] = params[
                        "p_storage_auth_key_id"
                    ]
                    db.state["storage_auth_tag"] = params[
                        "p_storage_auth_tag"
                    ]
                    db.sealed = True
                    return FakeTrustResult({
                        "status": "observed",
                        "generation": db.state["generation"],
                        "keyset_sha256": db.state["keyset_sha256"],
                    })
                if name == "shine_ai_trace_trust_advance_v3":
                    assert db.state is not None
                    assert (
                        db.state["generation"]
                        == params["p_expected_generation"]
                    )
                    assert (
                        db.state["keyset_sha256"]
                        == params["p_expected_keyset_sha256"]
                    )
                    db.state = {
                        "generation": params["p_next_generation"],
                        "keyset_sha256": params["p_next_keyset_sha256"],
                        "trusted_keyset": params["p_next_trusted_keyset"],
                        "source": "signed-transition",
                        "authorization_key_id": params[
                            "p_authorization_key_id"
                        ],
                        "authorization_public_key_sha256": params[
                            "p_authorization_public_key_sha256"
                        ],
                        "ledger_rows": db.state.get("ledger_rows", 1) + 1,
                        "state_sha256": params["p_state_sha256"],
                        "storage_auth_key_id": params[
                            "p_storage_auth_key_id"
                        ],
                        "storage_auth_tag": params[
                            "p_storage_auth_tag"
                        ],
                    }
                    db.sealed = True
                    return FakeTrustResult({
                        "status": "advanced",
                        "generation": params["p_next_generation"],
                        "keyset_sha256": params["p_next_keyset_sha256"],
                    })
                raise AssertionError(name)

        return Call()


class FakeCapabilityResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
        self.content = json.dumps(payload).encode("utf-8")
        self.headers = {
            "content-length": str(len(self.content)),
            "X-Shine-AI-Version": "1.40.0",
            "X-Shine-AI-Release": "1.40.0+test",
        }

    def json(self):
        return self._payload


def test_trace_keyset_discovery_requires_pin_and_caches_public_trust(monkeypatch):
    monkeypatch.setenv("SHINE_AI_BASE_URL", "https://shine-ai.example")
    monkeypatch.setenv("SHINE_AI_APP_ID", "shine-me")
    monkeypatch.setenv("SHINE_AI_APP_KEY_ID", "runtime-1")
    monkeypatch.setenv("SHINE_AI_APP_SECRET", "s" * 48)
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
        "trust": None,
    })
    db = FakeTrustDB()
    redis = FakeTrustRedis()
    payload = {
        "decision_trace_signing": {
            "enabled": True,
            "active_key_id": "trace-v1",
            "verification_keys": {
                "trace-v1": {
                    "public_key_b64": TRACE_PUBLIC_KEY_B64,
                    "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
                },
            },
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "keyset_generation": 1,
            "transition": None,
        },
    }
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        assert url == "https://shine-ai.example/v1/capabilities"
        assert kwargs["headers"]["X-Shine-App"] == "shine-me"
        assert "X-Shine-Signature" in kwargs["headers"]
        return FakeCapabilityResponse(payload)

    keyset, error, trust = runtime._shine_ai_verification_keyset(
        db,
        get_impl=fake_get,
        redis_client=redis,
    )
    assert error is None
    assert keyset["keyset_sha256"] == TRACE_SINGLE_KEYSET_SHA256
    assert keyset["generation"] == 1
    assert trust["status"] == "trusted"
    assert trust["acceptance_mode"] == "genesis-pin"
    assert db.state["keyset_sha256"] == TRACE_SINGLE_KEYSET_SHA256
    assert len(calls) == 1

    cached, error, cached_trust = runtime._shine_ai_verification_keyset(
        db,
        get_impl=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("cached trust must not refetch")
        ),
        redis_client=redis,
    )
    assert error is None
    assert cached == keyset
    assert cached_trust == trust
    assert len(calls) == 1

    # Simulate a process restart: cache is empty but the durable ledger remains.
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
        "trust": None,
    })
    reloaded, error, reloaded_trust = runtime._shine_ai_verification_keyset(
        db,
        get_impl=fake_get,
        redis_client=redis,
    )
    assert error is None
    assert reloaded == keyset
    assert reloaded_trust["acceptance_mode"] == "existing-ledger"
    assert len(calls) == 2


def test_trace_keyset_discovery_fails_closed_without_independent_pin(monkeypatch):
    monkeypatch.delenv("SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256", raising=False)
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
        "trust": None,
    })

    keyset, error, trust = runtime._shine_ai_verification_keyset(
        FakeTrustDB(),
        get_impl=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("unpinned trust must not contact service")
        ),
    )

    assert keyset is None
    assert error == "trace-keyset-pin-unavailable"
    assert trust["status"] == "unavailable"


def test_invalid_signature_authenticity_becomes_recovery_degradation():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["decision_trace_authenticity"] = {
        "version": "shine-ai/decision-trace-authenticity-v1",
        "status": "invalid",
        "authenticated": False,
        "reason_code": "decision-trace-signature-verification-failed",
    }

    recovery = runtime.build_runtime_recovery(
        packet,
        {"status": "not_required"},
        final=True,
    )
    status = runtime.build_human_status(
        packet,
        {"status": "not_required"},
        final=True,
    )

    assert recovery["mode"] == "degraded"
    assert recovery["stage"] == "authenticity"
    assert "authenticity-degraded" in recovery["reason_codes"]
    assert status["state"] == "degraded"
    assert "shine_ai" not in json.dumps(status)


def test_runtime_trace_binds_authenticity_without_signature_bytes():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["decision_trace_signature"] = {
        "signature_b64": "PRIVATE-SIGNATURE-BYTES",
    }
    first = runtime.build_runtime_trace(packet, {"status": "not_required"})

    changed = json.loads(json.dumps(packet))
    changed["components"]["shine_ai"]["decision_trace_authenticity"]["status"] = "invalid"
    changed["components"]["shine_ai"]["decision_trace_authenticity"]["authenticated"] = False
    second = runtime.build_runtime_trace(changed, {"status": "not_required"})

    assert first["version"] == "shine/runtime-trace-v8"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-SIGNATURE-BYTES" not in json.dumps(first)
    assert "PRIVATE-SIGNATURE-BYTES" not in json.dumps(second)



def test_signed_transition_advances_durable_trust_once(monkeypatch):
    previous = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "trusted_keyset": previous,
        "source": "genesis-pin",
    })
    redis = FakeTrustRedis()
    seed_checkpoint(redis, previous)
    next_keyset = {
        "active_key_id": "trace-v2",
        "verification_keys": {
            "trace-v2": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 2,
    }
    # Use a distinct valid digest in this orchestration test; cryptographic
    # transition correctness is independently tested in the verifier suite.
    next_keyset["keyset_sha256"] = runtime._canonical_sha256({
        "version": 1,
        "keys": next_keyset["verification_keys"],
    })
    monkeypatch.setattr(
        runtime,
        "verify_keyset_transition",
        lambda previous_keyset, candidate, transition: {
            "version": "shine-ai/decision-trace-keyset-continuity-v1",
            "status": "verified",
            "verified": True,
            "from_generation": 1,
            "to_generation": 2,
            "from_keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "to_keyset_sha256": candidate["keyset_sha256"],
            "authorization_key_id": "trace-v1",
            "authorization_public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            "certificate_sha256": "d" * 64,
        },
    )

    trusted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        next_keyset,
        {"certificate": "fixture"},
        redis_client=redis,
    )

    assert error is None
    assert trusted == next_keyset
    assert trust["status"] == "trusted"
    assert trust["acceptance_mode"] == "signed-transition"
    assert db.state["generation"] == 2
    assert db.rpc_calls[-1][0] == "shine_ai_trace_trust_snapshot_v3"


def test_keyset_generation_skip_is_rejected_before_ledger_mutation():
    previous = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "trusted_keyset": previous,
        "source": "genesis-pin",
    })
    skipped = dict(previous)
    skipped["generation"] = 3

    trusted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        skipped,
        None,
    )

    assert trusted is None
    assert error == "trace-keyset-generation-skip"
    assert trust["status"] == "invalid"
    assert all(
        name == "shine_ai_trace_trust_snapshot_v3"
        for name, _params in db.rpc_calls
    )


def test_invalid_trust_continuity_degrades_human_status():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["decision_trace_trust"] = {
        "status": "invalid",
        "reason_code": "keyset-transition-signature-verification-failed",
    }

    recovery = runtime.build_runtime_recovery(
        packet,
        {"status": "not_required"},
        final=True,
    )
    status = runtime.build_human_status(
        packet,
        {"status": "not_required"},
        final=True,
    )

    assert recovery["mode"] == "degraded"
    assert recovery["stage"] == "trust-continuity"
    assert "trust-continuity-degraded" in recovery["reason_codes"]
    assert status["state"] == "degraded"


def test_runtime_trace_binds_trust_generation_without_certificate_signature():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["decision_trace_trust"] = {
        "version": "shine-ai/decision-trace-keyset-continuity-v1",
        "status": "trusted",
        "acceptance_mode": "signed-transition",
        "generation": 2,
        "from_generation": 1,
        "to_generation": 2,
        "from_keyset_sha256": "a" * 64,
        "to_keyset_sha256": "b" * 64,
        "authorization_key_id": "trace-v1",
        "authorization_public_key_sha256": "c" * 64,
        "certificate_sha256": "d" * 64,
        "signature_b64": "PRIVATE-CERTIFICATE-SIGNATURE",
    }
    first = runtime.build_runtime_trace(packet, {"status": "not_required"})

    changed = json.loads(json.dumps(packet))
    changed["components"]["shine_ai"]["decision_trace_trust"]["generation"] = 3
    second = runtime.build_runtime_trace(changed, {"status": "not_required"})

    assert first["version"] == "shine/runtime-trace-v8"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-CERTIFICATE-SIGNATURE" not in json.dumps(first)


def test_persisted_trust_rejects_valid_older_generation_as_rollback():
    trusted_keyset = {
        "active_key_id": "trace-v2",
        "verification_keys": {
            "trace-v2": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": "",
        "generation": 2,
    }
    trusted_keyset["keyset_sha256"] = runtime._canonical_sha256({
        "version": 1,
        "keys": trusted_keyset["verification_keys"],
    })
    db = FakeTrustDB({
        "generation": 2,
        "keyset_sha256": trusted_keyset["keyset_sha256"],
        "trusted_keyset": trusted_keyset,
        "source": "signed-transition",
        "ledger_rows": 2,
    })
    older = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }

    accepted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        older,
        None,
    )

    assert accepted is None
    assert error == "trace-keyset-rollback-detected"
    assert trust["status"] == "invalid"
    assert trust["trusted_generation"] == 2
    assert trust["candidate_generation"] == 1
    assert all(
        name == "shine_ai_trace_trust_snapshot_v3"
        for name, _params in db.rpc_calls
    )


def test_persisted_trust_rejects_same_generation_keyset_fork():
    trusted = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "trusted_keyset": trusted,
        "source": "genesis-pin",
        "ledger_rows": 1,
    })
    fork = {
        "active_key_id": "trace-fork",
        "verification_keys": {
            "trace-fork": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": "",
        "generation": 1,
    }
    fork["keyset_sha256"] = runtime._canonical_sha256({
        "version": 1,
        "keys": fork["verification_keys"],
    })

    accepted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        fork,
        None,
    )

    assert accepted is None
    assert error == "trace-keyset-equivocation-detected"
    assert trust["status"] == "invalid"
    assert all(
        name == "shine_ai_trace_trust_snapshot_v3"
        for name, _params in db.rpc_calls
    )


def test_runtime_refuses_inconsistent_persisted_high_water_state():
    db = FakeTrustDB(
        inconsistent_reason="trust-generation-high-water-mismatch"
    )
    candidate = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }

    accepted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        candidate,
        None,
    )

    assert accepted is None
    assert error == "trust-generation-high-water-mismatch"
    assert trust["status"] == "invalid"
    assert trust["reason_code"] == "trust-generation-high-water-mismatch"


def test_automatic_genesis_bootstrap_never_starts_from_later_generation(
    monkeypatch,
):
    candidate = {
        "active_key_id": "trace-v2",
        "verification_keys": {
            "trace-v2": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": "",
        "generation": 2,
    }
    candidate["keyset_sha256"] = runtime._canonical_sha256({
        "version": 1,
        "keys": candidate["verification_keys"],
    })
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        candidate["keyset_sha256"],
    )
    db = FakeTrustDB()

    accepted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        candidate,
        None,
    )

    assert accepted is None
    assert error == "trace-keyset-genesis-generation-invalid"
    assert trust["status"] == "invalid"
    assert all(
        name == "shine_ai_trace_trust_snapshot_v3"
        for name, _params in db.rpc_calls
    )



def test_existing_generation_one_is_sealed_and_checkpointed(monkeypatch):
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    keyset = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    db = FakeTrustDB(
        {
            "generation": 1,
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "trusted_keyset": keyset,
            "source": "genesis-pin",
            "ledger_rows": 1,
        },
        sealed=False,
    )
    redis = FakeTrustRedis()

    sealed, error = runtime._seal_existing_trace_trust_state(
        db,
        redis_client=redis,
    )

    assert error is None
    assert sealed is not None
    assert db.sealed is True
    assert sealed["storage"]["status"] == "verified"
    assert (
        sealed["storage"]["independent_retention"]
        == "railway-redis-volume"
    )
    assert any(
        name == "shine_ai_trace_trust_seal_v3"
        for name, _params in db.rpc_calls
    )
    checkpoint = trust_storage.read_rollback_checkpoint(
        redis_client=redis
    )
    assert checkpoint["generation"] == 1
    assert checkpoint["keyset_sha256"] == TRACE_SINGLE_KEYSET_SHA256


def test_authenticated_state_rejects_database_tag_tampering():
    keyset = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "trusted_keyset": keyset,
        "source": "genesis-pin",
        "ledger_rows": 1,
    })
    redis = FakeTrustRedis()
    seed_checkpoint(redis, keyset)
    db.state["storage_auth_tag"] = "0" * 64

    state, error = runtime._trace_trust_state(
        db,
        redis_client=redis,
    )

    assert state is None
    assert error == "trust-state-envelope-auth-failed"


def test_independent_checkpoint_rejects_rolled_back_database():
    current = {
        "active_key_id": "trace-v2",
        "verification_keys": {
            "trace-v2": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": "",
        "generation": 2,
    }
    current["keyset_sha256"] = runtime._canonical_sha256({
        "version": 1,
        "keys": current["verification_keys"],
    })
    older = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    redis = FakeTrustRedis()
    seed_checkpoint(redis, current)
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "trusted_keyset": older,
        "source": "genesis-pin",
        "ledger_rows": 1,
    })

    state, error = runtime._trace_trust_state(
        db,
        redis_client=redis,
    )

    assert state is None
    assert error == "trust-checkpoint-rollback-detected"


def test_runtime_trace_binds_storage_proof_without_hmac_tag_or_redis_url():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["decision_trace_trust"] = {
        "status": "trusted",
        "acceptance_mode": "existing-ledger",
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "state_sha256": "a" * 64,
        "storage_auth_key_id": "storage-a",
        "checkpoint_mode": "existing-checkpoint",
        "storage_authenticated": True,
        "checkpoint_independent": True,
        "storage_auth_tag": "PRIVATE-HMAC-TAG",
        "redis_url": "PRIVATE-REDIS-URL",
    }
    first = runtime.build_runtime_trace(
        packet,
        {"status": "not_required"},
    )

    changed = json.loads(json.dumps(packet))
    changed["components"]["shine_ai"]["decision_trace_trust"][
        "state_sha256"
    ] = "b" * 64
    second = runtime.build_runtime_trace(
        changed,
        {"status": "not_required"},
    )

    rendered = json.dumps(first)
    assert first["version"] == "shine/runtime-trace-v8"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-HMAC-TAG" not in rendered
    assert "PRIVATE-REDIS-URL" not in rendered



def test_required_external_witness_cannot_be_missing_from_cached_trust(
    monkeypatch,
):
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    monkeypatch.setenv(
        "SHINE_FOUNDATION_TRUST_WITNESS_REQUIRED",
        "true",
    )
    keyset = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    redis = FakeTrustRedis()
    seed_checkpoint(redis, keyset)
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": float("inf"),
        "pin": TRACE_SINGLE_KEYSET_SHA256,
        "keyset": keyset,
        "trust": {
            "status": "trusted",
            "acceptance_mode": "existing-ledger",
        },
    })

    trusted, error, trust = runtime._shine_ai_verification_keyset(
        FakeTrustDB({
            "generation": 1,
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "trusted_keyset": keyset,
            "source": "genesis-pin",
            "ledger_rows": 1,
        }),
        redis_client=redis,
    )

    assert trusted is None
    assert error == "foundation-witness-unverified"
    assert trust["status"] == "invalid"


def test_runtime_trace_binds_external_witness_without_foundation_auth_tag():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["decision_trace_trust"] = {
        "status": "trusted",
        "acceptance_mode": "existing-ledger",
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "state_sha256": "a" * 64,
        "storage_authenticated": True,
        "checkpoint_independent": True,
        "external_witness": {
            "status": "verified",
            "witness_id": "foundation-project-l",
            "sequence": 1,
            "head_sha256": "b" * 64,
            "generation": 1,
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "state_sha256": "a" * 64,
            "auth_key_id": "foundation-witness-v1",
            "mode": "existing-witness",
            "independent_retention": "foundation-supabase",
            "history_status": "verified",
            "chain_version": 1,
            "previous_chain_tag": "0" * 64,
            "chain_tag": "d" * 64,
            "authTag": "PRIVATE-FOUNDATION-HMAC",
        },
    }
    first = runtime.build_runtime_trace(
        packet,
        {"status": "not_required"},
    )

    changed = json.loads(json.dumps(packet))
    changed["components"]["shine_ai"]["decision_trace_trust"][
        "external_witness"
    ]["chain_tag"] = "e" * 64
    second = runtime.build_runtime_trace(
        changed,
        {"status": "not_required"},
    )

    rendered = json.dumps(first)
    assert first["version"] == "shine/runtime-trace-v8"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-FOUNDATION-HMAC" not in rendered



def test_required_witness_quorum_cannot_be_missing_from_cached_trust(
    monkeypatch,
):
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_REQUIRED",
        "true",
    )
    keyset = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    redis = FakeTrustRedis()
    seed_checkpoint(redis, keyset)
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": float("inf"),
        "pin": TRACE_SINGLE_KEYSET_SHA256,
        "keyset": keyset,
        "trust": {
            "status": "trusted",
            "acceptance_mode": "existing-ledger",
            "external_witness": {
                "status": "verified",
                "witness_id": "foundation-project-l",
            },
        },
    })

    trusted, error, trust = runtime._shine_ai_verification_keyset(
        FakeTrustDB({
            "generation": 1,
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "trusted_keyset": keyset,
            "source": "genesis-pin",
            "ledger_rows": 1,
        }),
        redis_client=redis,
    )

    assert trusted is None
    assert error == "trust-witness-quorum-unverified"
    assert trust["status"] == "invalid"


def test_cached_quorum_without_foundation_chain_fails_closed(
    monkeypatch,
):
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_REQUIRED",
        "true",
    )
    keyset = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    redis = FakeTrustRedis()
    seed_checkpoint(redis, keyset)
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": float("inf"),
        "pin": TRACE_SINGLE_KEYSET_SHA256,
        "keyset": keyset,
        "trust": {
            "status": "trusted",
            "acceptance_mode": "existing-ledger",
            "witness_quorum": {
                "status": "verified",
                "minimum_witnesses": 2,
                "verified_witness_count": 2,
                "sequence": 1,
            },
        },
    })

    trusted, error, trust = runtime._shine_ai_verification_keyset(
        FakeTrustDB({
            "generation": 1,
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "trusted_keyset": keyset,
            "source": "genesis-pin",
            "ledger_rows": 1,
        }),
        redis_client=redis,
    )

    assert trusted is None
    assert error == "trust-witness-foundation-chain-unverified"
    assert trust["status"] == "invalid"


def test_cached_external_witness_without_chain_fails_closed(
    monkeypatch,
):
    monkeypatch.delenv(
        "SHINE_TRACE_WITNESS_QUORUM_REQUIRED",
        raising=False,
    )
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    monkeypatch.setenv(
        "SHINE_FOUNDATION_TRUST_WITNESS_REQUIRED",
        "true",
    )
    keyset = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    redis = FakeTrustRedis()
    seed_checkpoint(redis, keyset)
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": float("inf"),
        "pin": TRACE_SINGLE_KEYSET_SHA256,
        "keyset": keyset,
        "trust": {
            "status": "trusted",
            "acceptance_mode": "existing-ledger",
            "external_witness": {
                "status": "verified",
                "witness_id": "foundation-project-l",
                "sequence": 1,
            },
        },
    })

    trusted, error, trust = runtime._shine_ai_verification_keyset(
        FakeTrustDB({
            "generation": 1,
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "trusted_keyset": keyset,
            "source": "genesis-pin",
            "ledger_rows": 1,
        }),
        redis_client=redis,
    )

    assert trusted is None
    assert error == "foundation-witness-chain-unverified"
    assert trust["status"] == "invalid"


def test_fresh_trust_attaches_verified_witness_quorum(monkeypatch):
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_REQUIRED",
        "true",
    )
    monkeypatch.setenv(
        "SHINE_AI_BASE_URL",
        "https://shine-ai.example",
    )
    monkeypatch.setenv("SHINE_AI_APP_ID", "shine-me")
    monkeypatch.setenv("SHINE_AI_APP_KEY_ID", "runtime-1")
    monkeypatch.setenv("SHINE_AI_APP_SECRET", "s" * 48)

    keyset = {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": 1,
    }
    redis = FakeTrustRedis()
    seed_checkpoint(redis, keyset)
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "trusted_keyset": keyset,
        "source": "genesis-pin",
        "ledger_rows": 1,
    })
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
        "trust": None,
    })

    monkeypatch.setattr(
        runtime,
        "_accept_trace_keyset_candidate",
        lambda *_args, **_kwargs: (
            keyset,
            None,
            {
                "status": "trusted",
                "acceptance_mode": "existing-ledger",
            },
        ),
    )
    quorum_receipt = {
        "status": "verified",
        "policy_generation": 1,
        "policy_sha256": "a" * 64,
        "minimum_witnesses": 2,
        "verified_witness_count": 2,
        "witness_ids": [
            "foundation-project-l",
            "redis-project-l",
        ],
        "sequence": 1,
        "head_sha256": "b" * 64,
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "state_sha256": "c" * 64,
        "independence": [
            "foundation-supabase",
            "railway-redis-volume",
        ],
        "foundation_chain": {
            "status": "verified",
            "witness_id": "foundation-project-l",
            "chain_version": 1,
            "sequence": 1,
            "previous_chain_tag": "0" * 64,
            "chain_tag": "d" * 64,
        },
    }
    monkeypatch.setattr(
        runtime,
        "ensure_trust_witness_quorum",
        lambda *_args, **_kwargs: quorum_receipt,
    )

    payload = {
        "decision_trace_signing": {
            "enabled": True,
            "active_key_id": "trace-v1",
            "verification_keys": keyset["verification_keys"],
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "keyset_generation": 1,
            "transition": None,
        },
    }

    class CapabilityResponse:
        status_code = 200
        content = json.dumps(payload).encode("utf-8")
        headers = {
            "content-length": str(len(content)),
        }

        @staticmethod
        def json():
            return payload

    trusted, error, trust = runtime._shine_ai_verification_keyset(
        db,
        redis_client=redis,
        get_impl=lambda *_args, **_kwargs: CapabilityResponse(),
    )

    assert error is None
    assert trusted == keyset
    assert trust["witness_quorum"] == quorum_receipt


def test_runtime_trace_binds_quorum_without_witness_hmac_tags():
    packet = runtime_for_human_status()
    packet["components"]["shine_ai"]["decision_trace_trust"] = {
        "status": "trusted",
        "acceptance_mode": "existing-ledger",
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "state_sha256": "a" * 64,
        "storage_authenticated": True,
        "checkpoint_independent": True,
        "witness_quorum": {
            "status": "verified",
            "policy_generation": 1,
            "policy_sha256": "b" * 64,
            "minimum_witnesses": 2,
            "verified_witness_count": 2,
            "witness_ids": [
                "foundation-project-l",
                "redis-project-l",
            ],
            "sequence": 4,
            "head_sha256": "c" * 64,
            "generation": 1,
            "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
            "state_sha256": "a" * 64,
            "independence": [
                "foundation-supabase",
                "railway-redis-volume",
            ],
            "foundation_chain": {
                "status": "verified",
                "witness_id": "foundation-project-l",
                "chain_version": 1,
                "sequence": 4,
                "previous_chain_tag": "d" * 64,
                "chain_tag": "e" * 64,
                "auth_tag": "PRIVATE-CHAIN-HMAC",
            },
            "foundation_auth_tag": "PRIVATE-FOUNDATION-HMAC",
            "redis_auth_tag": "PRIVATE-REDIS-HMAC",
        },
    }

    first = runtime.build_runtime_trace(
        packet,
        {"status": "not_required"},
    )
    changed = json.loads(json.dumps(packet))
    changed["components"]["shine_ai"]["decision_trace_trust"][
        "witness_quorum"
    ]["foundation_chain"]["chain_tag"] = "f" * 64
    second = runtime.build_runtime_trace(
        changed,
        {"status": "not_required"},
    )

    rendered = json.dumps(first)
    assert first["version"] == "shine/runtime-trace-v8"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-FOUNDATION-HMAC" not in rendered
    assert "PRIVATE-REDIS-HMAC" not in rendered
    assert "PRIVATE-CHAIN-HMAC" not in rendered

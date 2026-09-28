import hashlib
import hmac
import json

from services import shine_runtime_service as runtime


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

    assert first["version"] == "shine/runtime-trace-v5"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-REASON-TEXT-NOT-HASHED" not in json.dumps(second)



TRACE_PUBLIC_KEY_B64 = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
TRACE_PUBLIC_KEY_SHA256 = "56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c"
TRACE_SINGLE_KEYSET_SHA256 = "00d100d5873dd2fecc3049dc501b2f2f5dfc268710858b9cf68b0f5858666f4a"


class FakeTrustResult:
    def __init__(self, data):
        self.data = data


class FakeTrustDB:
    def __init__(self, state=None):
        self.state = state
        self.rpc_calls = []
        self._table = None

    def table(self, name):
        assert name == "shine_ai_trace_trust_state"
        self._table = name
        return self

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return FakeTrustResult([self.state] if self.state else [])

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        db = self

        class Call:
            def execute(self):
                if name == "shine_ai_trace_trust_bootstrap_v1":
                    db.state = {
                        "generation": params["p_generation"],
                        "keyset_sha256": params["p_keyset_sha256"],
                        "trusted_keyset": params["p_trusted_keyset"],
                        "source": params["p_source"],
                    }
                    return FakeTrustResult({
                        "status": "trusted",
                        "generation": params["p_generation"],
                        "keyset_sha256": params["p_keyset_sha256"],
                    })
                if name == "shine_ai_trace_trust_advance_v1":
                    db.state = {
                        "generation": params["p_next_generation"],
                        "keyset_sha256": params["p_next_keyset_sha256"],
                        "trusted_keyset": params["p_next_trusted_keyset"],
                        "source": "signed-transition",
                        "authorization_key_id": params["p_authorization_key_id"],
                        "authorization_public_key_sha256": params[
                            "p_authorization_public_key_sha256"
                        ],
                    }
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


def _layer142_capabilities(keyset, transition=None):
    return {
        "decision_trace_signing": {
            "enabled": True,
            "active_key_id": keyset["active_key_id"],
            "verification_keys": keyset["verification_keys"],
            "keyset_sha256": keyset["keyset_sha256"],
            "keyset_generation": keyset["generation"],
            "transition": transition,
            "transition_verification_supported": True,
            "client_trust_state_version": 1,
            "client_trust_state_supported": True,
            "rollback_protection_supported": True,
            "same_generation_equivocation_rejected": True,
            "keyset_fingerprint_excludes_active_key": True,
            "trust_anchor": "pin-keyset-sha256",
        },
    }


def _runtime_single_keyset(generation=1):
    return {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TRACE_PUBLIC_KEY_B64,
                "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "generation": generation,
    }


def _runtime_dual_keyset(active_key_id="trace-v1", generation=1):
    keys = {
        "trace-v1": {
            "public_key_b64": TRACE_PUBLIC_KEY_B64,
            "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
        },
        "trace-v2": {
            "public_key_b64": TRACE_PUBLIC_KEY_B64,
            "public_key_sha256": TRACE_PUBLIC_KEY_SHA256,
        },
    }
    return {
        "active_key_id": active_key_id,
        "verification_keys": keys,
        "keyset_sha256": runtime._canonical_sha256({
            "version": 1,
            "keys": keys,
        }),
        "generation": generation,
    }


def test_trace_keyset_discovery_bootstraps_then_reobserves_every_time(monkeypatch):
    monkeypatch.setenv("SHINE_AI_BASE_URL", "https://shine-ai.example")
    monkeypatch.setenv("SHINE_AI_APP_ID", "shine-me")
    monkeypatch.setenv("SHINE_AI_APP_KEY_ID", "runtime-1")
    monkeypatch.setenv("SHINE_AI_APP_SECRET", "s" * 48)
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        TRACE_SINGLE_KEYSET_SHA256,
    )
    db = FakeTrustDB()
    keyset = _runtime_single_keyset()
    payload = _layer142_capabilities(keyset)
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        assert url == "https://shine-ai.example/v1/capabilities"
        assert kwargs["headers"]["X-Shine-App"] == "shine-me"
        assert "X-Shine-Signature" in kwargs["headers"]
        return FakeCapabilityResponse(payload)

    first, error, trust = runtime._shine_ai_verification_keyset(
        db,
        get_impl=fake_get,
    )
    assert error is None
    assert first == keyset
    assert trust["acceptance_mode"] == "genesis-pin"
    assert trust["anti_rollback"] is True
    assert db.state["keyset_sha256"] == TRACE_SINGLE_KEYSET_SHA256
    assert len(calls) == 1

    # Security decisions must re-observe capabilities rather than trust cache.
    second, error, second_trust = runtime._shine_ai_verification_keyset(
        db,
        get_impl=fake_get,
    )
    assert error is None
    assert second == keyset
    assert second_trust["acceptance_mode"] == "existing-ledger"
    assert len(calls) == 2

    # Genesis pin is no longer an availability dependency once trust is persisted.
    monkeypatch.delenv("SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256", raising=False)
    third, error, third_trust = runtime._shine_ai_verification_keyset(
        db,
        get_impl=fake_get,
    )
    assert error is None
    assert third == keyset
    assert third_trust["acceptance_mode"] == "existing-ledger"
    assert len(calls) == 3


def test_trace_keyset_discovery_requires_pin_for_empty_generation1_state(monkeypatch):
    monkeypatch.setenv("SHINE_AI_BASE_URL", "https://shine-ai.example")
    monkeypatch.setenv("SHINE_AI_APP_ID", "shine-me")
    monkeypatch.setenv("SHINE_AI_APP_KEY_ID", "runtime-1")
    monkeypatch.setenv("SHINE_AI_APP_SECRET", "s" * 48)
    monkeypatch.delenv("SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256", raising=False)
    payload = _layer142_capabilities(_runtime_single_keyset())

    keyset, error, trust = runtime._shine_ai_verification_keyset(
        FakeTrustDB(),
        get_impl=lambda *args, **kwargs: FakeCapabilityResponse(payload),
    )

    assert keyset is None
    assert error == "trace-keyset-pin-unavailable"
    assert trust["status"] == "unavailable"
    assert trust["anti_rollback"] is True


def test_later_generation_cannot_bootstrap_from_pin(monkeypatch):
    candidate = _runtime_dual_keyset(generation=2)
    monkeypatch.setenv(
        "SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256",
        candidate["keyset_sha256"],
    )
    db = FakeTrustDB()

    trusted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        candidate,
        None,
    )

    assert trusted is None
    assert error == "trace-keyset-genesis-generation-required"
    assert trust["candidate_generation"] == 2
    assert db.rpc_calls == []


def test_persisted_trust_state_is_revalidated_before_use():
    candidate = _runtime_single_keyset()
    tampered = dict(candidate)
    tampered["generation"] = 2
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": TRACE_SINGLE_KEYSET_SHA256,
        "trusted_keyset": tampered,
        "source": "genesis-pin",
    })

    trusted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        candidate,
        None,
    )

    assert trusted is None
    assert error == "trace-keyset-persisted-state-invalid"
    assert trust["persisted_state_valid"] is False
    assert db.rpc_calls == []


def test_valid_older_generation_is_rejected_as_rollback():
    current = _runtime_dual_keyset(generation=2)
    db = FakeTrustDB({
        "generation": 2,
        "keyset_sha256": current["keyset_sha256"],
        "trusted_keyset": current,
        "source": "signed-transition",
    })
    older = _runtime_single_keyset(generation=1)

    trusted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        older,
        None,
    )

    assert trusted is None
    assert error == "trace-keyset-rollback"
    assert trust["rollback_rejected"] is True
    assert trust["trusted_generation"] == 2
    assert trust["candidate_generation"] == 1
    assert db.rpc_calls == []


def test_same_generation_different_keyset_is_rejected_as_equivocation():
    current = _runtime_single_keyset(generation=1)
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": current["keyset_sha256"],
        "trusted_keyset": current,
        "source": "genesis-pin",
    })
    fork = _runtime_dual_keyset(generation=1)

    trusted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        fork,
        None,
    )

    assert trusted is None
    assert error == "trace-keyset-same-generation-equivocation"
    assert trust["equivocation_rejected"] is True
    assert db.rpc_calls == []


def test_same_generation_active_key_flip_is_valid_without_new_generation():
    current = _runtime_dual_keyset(active_key_id="trace-v1", generation=1)
    db = FakeTrustDB({
        "generation": 1,
        "keyset_sha256": current["keyset_sha256"],
        "trusted_keyset": current,
        "source": "genesis-pin",
    })
    flipped = _runtime_dual_keyset(active_key_id="trace-v2", generation=1)

    trusted, error, trust = runtime._accept_trace_keyset_candidate(
        db,
        flipped,
        None,
    )

    assert error is None
    assert trusted == flipped
    assert trust["acceptance_mode"] == "existing-ledger"
    assert trust["generation"] == 1
    assert trust["equivocation_rejected"] is False
    assert db.rpc_calls == []


def test_live_capability_observation_detects_rollback_after_newer_state(monkeypatch):
    monkeypatch.setenv("SHINE_AI_BASE_URL", "https://shine-ai.example")
    monkeypatch.setenv("SHINE_AI_APP_ID", "shine-me")
    monkeypatch.setenv("SHINE_AI_APP_KEY_ID", "runtime-1")
    monkeypatch.setenv("SHINE_AI_APP_SECRET", "s" * 48)
    monkeypatch.delenv("SHINE_AI_TRACE_ACCEPTED_KEYSET_SHA256", raising=False)

    current = _runtime_dual_keyset(generation=2)
    db = FakeTrustDB({
        "generation": 2,
        "keyset_sha256": current["keyset_sha256"],
        "trusted_keyset": current,
        "source": "signed-transition",
    })
    older_payload = _layer142_capabilities(
        _runtime_single_keyset(generation=1)
    )

    trusted, error, trust = runtime._shine_ai_verification_keyset(
        db,
        get_impl=lambda *args, **kwargs: FakeCapabilityResponse(older_payload),
    )

    assert trusted is None
    assert error == "trace-keyset-rollback"
    assert trust["rollback_rejected"] is True


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

    assert first["version"] == "shine/runtime-trace-v5"
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
    )

    assert error is None
    assert trusted == next_keyset
    assert trust["status"] == "trusted"
    assert trust["acceptance_mode"] == "signed-transition"
    assert db.state["generation"] == 2
    assert db.rpc_calls[-1][0] == "shine_ai_trace_trust_advance_v1"


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
    assert db.rpc_calls == []


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

    assert first["version"] == "shine/runtime-trace-v5"
    assert first["lineage_sha256"] != second["lineage_sha256"]
    assert "PRIVATE-CERTIFICATE-SIGNATURE" not in json.dumps(first)

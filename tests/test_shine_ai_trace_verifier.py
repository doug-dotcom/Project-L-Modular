import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.shine_ai_trace_verifier import (
    digest_verification_keyset,
    verify_decision_trace,
    verify_decision_trace_authenticity,
)


def response_fixture():
    contract = "a" * 64
    return {
        "response_profile_contract_sha256": contract,
        "planning": {
            "version": 1,
            "tool_source": "server",
            "selected_tools": ["calculator"],
            "memory_source": "server",
            "selected_memory": {"project-l": ["sport", "episodic"]},
            "route": "model",
            "provider": "fake",
            "model": "fake-fast",
            "model_tier": "fast",
            "routing_score": 0,
            "max_output_tokens": 600,
            "context_budget_chars": 4000,
            "context_budget_items": 5,
            "deferred_controls": ["context-selection", "request-cost"],
            "reasons": ["Private server prose is not attested."],
        },
        "recovery": {
            "version": 1,
            "mode": "not-needed",
            "failure_stage": None,
            "action": "none",
            "automatic_retry_count": 0,
            "reason": "Private recovery prose.",
        },
        "execution": {
            "version": 1,
            "status": "adjusted",
            "route": "model",
            "provider": "fake",
            "model": "fake-fast-2026-09-28",
            "model_tier": "fast",
            "max_output_tokens": 200,
            "tools": ["calculator"],
            "memory": {"project-l": ["episodic", "sport"]},
            "context_budget_chars": 4000,
            "context_budget_items": 5,
            "adjustments": [
                "provider-resolved-model",
                "output-token-tightened",
            ],
        },
        "grounding": {
            "evidence_available": True,
            "selected_evidence_ids": ["memory:project-l:PRIVATE"],
            "cited_evidence_ids": ["memory:project-l:PRIVATE"],
            "unknown_citation_ids": [],
            "citation_coverage": 1.0,
        },
        "verification": {
            "mode": "verified",
            "evidence_required": True,
            "evidence_available": True,
            "cited_evidence_count": 1,
            "unknown_citation_count": 0,
            "required_memory_sources": ["project-l"],
            "cited_memory_sources": ["project-l"],
            "required_tool_request_ids": ["PRIVATE-TOOL-ID"],
            "cited_tool_request_ids": ["PRIVATE-TOOL-ID"],
            "warnings": [],
        },
        "delivery": {
            "mode": "normal",
            "reason": "Private delivery prose.",
        },
        "decision_trace": {
            "version": 1,
            "algorithm": "sha256",
            "scope": "control-plane",
            "service_version": "1.37.0",
            "service_release": "1.37.0+git.abcdef123456",
            "response_profile_contract_sha256": contract,
            "planning_sha256": "68d464a80cd82787eb5c5391d86e4a9b7dc477f67d3d4bb82ee596cdd8c93f9d",
            "recovery_sha256": "c690b4050317e031dab631f91e4832e9da49b0b8e02ad9d16288a4f76e0af44d",
            "execution_sha256": "063db9b91b9c8a6878066453a499b98202a21b7ce4972e0ec1b2bce5c49f3d36",
            "grounding_sha256": "ca6fc17368ae4d4afae24d5dcfc62e6d3f1021c5b800ac211c1c864efd5ba48a",
            "verification_sha256": "b5c8fbc43fe35b5fb30affdddfa2cb61716666f5b2d1f796a0b66f314359297e",
            "delivery_sha256": "fa76e6a145e80d3ef8d955abd5a17426feba569df832d2cf6af7dbd5b86c5240",
            "lineage_sha256": "9b22f32294c8ab531135a1c7d3326d470d11024f6b8a7a066bff67b0a1d944ff",
        },
    }


def test_independent_verifier_matches_shine_ai_golden_vector():
    result = verify_decision_trace(
        response_fixture(),
        header_version="1.37.0",
        header_release="1.37.0+git.abcdef123456",
    )

    assert result["status"] == "verified"
    assert result["verified"] is True
    assert result["lineage_sha256"] == (
        "9b22f32294c8ab531135a1c7d3326d470d11024f6b8a7a066bff67b0a1d944ff"
    )


def test_independent_verifier_detects_control_plane_tampering():
    payload = response_fixture()
    payload["execution"]["max_output_tokens"] = 201

    result = verify_decision_trace(payload)

    assert result["status"] == "invalid"
    assert result["verified"] is False
    assert result["reason_code"] == "decision-trace-digest-mismatch"
    assert result["recomputed_lineage_sha256"] != result["lineage_sha256"]


def test_independent_verifier_binds_service_headers():
    result = verify_decision_trace(
        response_fixture(),
        header_version="1.38.0",
        header_release="1.37.0+git.abcdef123456",
    )

    assert result["status"] == "invalid"
    assert result["reason_code"] == "decision-trace-version-header-mismatch"


def test_private_evidence_ids_do_not_affect_verified_trace():
    payload = response_fixture()
    payload["grounding"]["selected_evidence_ids"] = ["memory:project-l:OTHER-PRIVATE"]
    payload["grounding"]["cited_evidence_ids"] = ["memory:project-l:OTHER-PRIVATE"]
    payload["verification"]["required_tool_request_ids"] = ["OTHER-PRIVATE-TOOL"]
    payload["verification"]["cited_tool_request_ids"] = ["OTHER-PRIVATE-TOOL"]

    result = verify_decision_trace(payload)

    assert result["status"] == "verified"
    assert result["verified"] is True



def test_live_verifier_requires_response_identity_headers():
    result = verify_decision_trace(
        response_fixture(),
        require_response_identity=True,
    )

    assert result["status"] == "invalid"
    assert result["reason_code"] == "decision-trace-response-identity-missing"


TEST_PRIVATE_KEY_B64 = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
TEST_PUBLIC_KEY_B64 = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
TEST_PUBLIC_KEY_SHA256 = "56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c"
TEST_PUBLIC_KEY_V2_B64 = "Kay64UG8yvCyLhqU000LxzYeUm0L/hLIl5S8kyKWbdc="
TEST_PUBLIC_KEY_V2_SHA256 = "24f6ed6acbfe1009c030d7ca567c33ca4830911498236b5561a6c82abec5de28"
SINGLE_KEYSET_SHA256 = "00d100d5873dd2fecc3049dc501b2f2f5dfc268710858b9cf68b0f5858666f4a"
OVERLAP_KEYSET_SHA256 = "5d9919a8cf9453a330016410e2903d7556a170d7ce95450dc4a90cab366cd9ca"


def single_keyset():
    return {
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TEST_PUBLIC_KEY_B64,
                "public_key_sha256": TEST_PUBLIC_KEY_SHA256,
            },
        },
        "keyset_sha256": SINGLE_KEYSET_SHA256,
    }


def overlap_keyset():
    return {
        "active_key_id": "trace-v2",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": TEST_PUBLIC_KEY_B64,
                "public_key_sha256": TEST_PUBLIC_KEY_SHA256,
            },
            "trace-v2": {
                "public_key_b64": TEST_PUBLIC_KEY_V2_B64,
                "public_key_sha256": TEST_PUBLIC_KEY_V2_SHA256,
            },
        },
        "keyset_sha256": OVERLAP_KEYSET_SHA256,
    }


def sign_fixture(payload, key_id="trace-v1"):
    private_bytes = base64.b64decode(TEST_PRIVATE_KEY_B64)
    signer = Ed25519PrivateKey.from_private_bytes(private_bytes)
    lineage = payload["decision_trace"]["lineage_sha256"]
    signature = signer.sign(
        (
            "shine-ai:decision-trace:v1\n"
            + key_id
            + "\n"
            + lineage
        ).encode("utf-8")
    )
    payload["decision_trace_signature"] = {
        "version": 1,
        "algorithm": "ed25519",
        "domain": "shine-ai:decision-trace:v1",
        "key_id": key_id,
        "public_key_sha256": TEST_PUBLIC_KEY_SHA256,
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }
    return payload


def test_keyset_digest_matches_shine_ai_layer140_golden_vectors():
    assert digest_verification_keyset(single_keyset()) == SINGLE_KEYSET_SHA256
    assert digest_verification_keyset(overlap_keyset()) == OVERLAP_KEYSET_SHA256


def test_authenticity_verifies_signed_independently_recomputed_trace():
    payload = sign_fixture(response_fixture())

    result = verify_decision_trace_authenticity(
        payload,
        trusted_keyset=single_keyset(),
        accepted_keyset_sha256=[SINGLE_KEYSET_SHA256],
        header_version="1.37.0",
        header_release="1.37.0+git.abcdef123456",
    )

    assert result["status"] == "authenticated"
    assert result["authenticated"] is True
    assert result["key_id"] == "trace-v1"
    assert result["keyset_sha256"] == SINGLE_KEYSET_SHA256
    assert result["lineage_sha256"] == payload["decision_trace"]["lineage_sha256"]


def test_overlap_keyset_accepts_old_signature_during_active_key_cutover():
    payload = sign_fixture(response_fixture(), "trace-v1")

    result = verify_decision_trace_authenticity(
        payload,
        trusted_keyset=overlap_keyset(),
        accepted_keyset_sha256=[OVERLAP_KEYSET_SHA256],
        header_version="1.37.0",
        header_release="1.37.0+git.abcdef123456",
    )

    assert result["status"] == "authenticated"
    assert result["key_id"] == "trace-v1"
    assert result["keyset_sha256"] == OVERLAP_KEYSET_SHA256


def test_authenticity_rejects_unpinned_or_tampered_signature():
    payload = sign_fixture(response_fixture())
    bad_pin = verify_decision_trace_authenticity(
        payload,
        trusted_keyset=single_keyset(),
        accepted_keyset_sha256=["f" * 64],
        header_version="1.37.0",
        header_release="1.37.0+git.abcdef123456",
    )
    assert bad_pin["status"] == "invalid"
    assert bad_pin["reason_code"] == "trusted-keyset-mismatch"

    payload["decision_trace_signature"]["signature_b64"] = "A" * 86 + "=="
    tampered = verify_decision_trace_authenticity(
        payload,
        trusted_keyset=single_keyset(),
        accepted_keyset_sha256=[SINGLE_KEYSET_SHA256],
        header_version="1.37.0",
        header_release="1.37.0+git.abcdef123456",
    )
    assert tampered["status"] == "invalid"
    assert tampered["reason_code"] == "decision-trace-signature-verification-failed"


def test_authenticity_requires_an_independent_keyset_pin():
    payload = sign_fixture(response_fixture())
    result = verify_decision_trace_authenticity(
        payload,
        trusted_keyset=single_keyset(),
        accepted_keyset_sha256=[],
        header_version="1.37.0",
        header_release="1.37.0+git.abcdef123456",
    )
    assert result["status"] == "unavailable"
    assert result["reason_code"] == "trusted-keyset-pin-unavailable"

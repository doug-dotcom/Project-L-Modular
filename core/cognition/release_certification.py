"""Layer 100: deterministic Project L release certification.

This is a runtime self-audit, not a claim of intelligence or human acceptance.
It verifies that critical safety/integrity mechanisms are wired and executable,
and keeps external/live acceptance explicitly separate.
"""

from __future__ import annotations

from hashlib import sha256
import json

from core.cognition.context_budget import (
    CONTEXT_BUDGET_VERSION,
    build_generation_cognitive_context,
)
from core.cognition.context_budget_trials import (
    VERSION as CONTEXT_TRIAL_VERSION,
    trial_manifest as context_trial_manifest,
)
from core.cognition.controller import CONTROLLER_VERSION
from core.cognition.delivery_integrity import (
    seal_chat_delivery_payload,
    verify_chat_delivery_payload,
)
from core.cognition.production_baseline import summarise_production_baseline
from core.cognition.publication_repair import (
    FINAL_PUBLICATION_STAGES,
    final_publication_stage_receipt,
    seal_final_publication_reply,
    sealed_reply_persistence_receipt,
    verify_final_publication_seal,
)
from core.cognition.runtime_safety import CORE_VERSION, cognitive_failsafe


LAYER = 100
VERSION = "layer100-release-certification-1"


def _result(name: str, passed: bool, *, scope: str, evidence: dict | None = None) -> dict:
    return {
        "name": name,
        "status": "verified" if passed else "failed",
        "passed": bool(passed),
        "scope": scope,
        "evidence": evidence or {},
    }


def _publication_and_delivery_check() -> dict:
    reply = "Layer 100 synthetic publication integrity check."
    reply_sha = sha256(reply.encode("utf-8")).hexdigest()
    audit = {"reply_sha256": reply_sha}

    stages = [
        final_publication_stage_receipt(stage, reply, reply)
        for stage in FINAL_PUBLICATION_STAGES
    ]
    publication = seal_final_publication_reply(
        reply,
        reply,
        audit,
        stages,
    )
    publication_check = verify_final_publication_seal(reply, publication)

    persistence = sealed_reply_persistence_receipt(
        reply,
        publication,
        {"last_reply_sha256": reply_sha},
        {
            "saved": True,
            "content_sha256": reply_sha,
            "stored_content_sha256": reply_sha,
            "integrity": "verified",
        },
        {"role": "assistant", "content": reply},
    )

    request_id = "layer100-synthetic-request"
    payload = seal_chat_delivery_payload(
        {
            "reply": reply,
            "server": "layer100-synthetic",
            "cognition": {
                "evidence_evaluation": {"final_publication": publication},
                "assistant_persistence": persistence,
            },
        },
        request_id=request_id,
    )
    delivery = verify_chat_delivery_payload(
        payload,
        expected_request_id=request_id,
    )

    return {
        "publication_valid": bool(
            publication.get("valid")
            and publication_check.get("valid")
        ),
        "persistence_verified": persistence.get("status") == "verified",
        "delivery_valid": bool(
            delivery.get("valid")
            and delivery.get("bound")
        ),
        "publication_stage_count": len(stages),
        "delivery_bound": bool(delivery.get("bound")),
    }


def _runtime_failsafe_check() -> dict:
    secret = "layer100-secret-error-detail"

    @cognitive_failsafe
    def broken(message: str, rhee_packet: dict):
        raise RuntimeError(secret)

    packet = broken("synthetic", {"context": ""})
    serialised = json.dumps(packet, sort_keys=True)
    runtime = packet.get("runtime") or {}
    diagnostic = runtime.get("diagnostic") or {}
    return {
        "degraded": runtime.get("status") == "degraded",
        "fallback_used": runtime.get("fallback_used") is True,
        "diagnostic_bounded": bool(
            diagnostic.get("error_type")
            and diagnostic.get("source_file")
            and diagnostic.get("source_function")
        ),
        "exception_message_hidden": secret not in serialised,
    }


def _context_budget_check() -> dict:
    marker = "LAYER100-INACTIVE-CONTEXT-MARKER"
    packet = {
        "engine": "project_l_cognitive_core",
        "version": CORE_VERSION,
        "runtime": {"status": "complete", "fallback_used": False},
        "controller": {
            "difficulty": "low",
            "needs": {
                "memory": False,
                "current_evidence": False,
                "external_evidence": False,
                "structured_reasoning": False,
                "longitudinal_reasoning": False,
                "specialist": False,
                "action": False,
            },
        },
        "route": {
            "rike": "not_required",
            "mary": "not_required",
            "confidence_evidence": "active",
        },
        "guardrails": {"passed": True, "issues": []},
        "confidence_dimensions": {"status": "complete"},
        "confidence_evidence": {"status": "complete"},
        "rike": {"status": "not_required", "detail": marker},
        "mary": {"active": False, "detail": marker},
        "working_memory": {"current_goal": "synthetic"},
        "model_independence": {"foundation_model_is_replaceable": True},
        "portability": {"status": "available"},
    }
    result = build_generation_cognitive_context(packet)
    receipt = result["receipt"]
    return {
        "mode": receipt.get("mode"),
        "marker_removed": marker not in result["context"],
        "required_context_preserved": receipt.get("required_context_preserved") is True,
        "rhee_evidence_modified": receipt.get("rhee_evidence_modified"),
        "stored_cognitive_packet_modified": receipt.get("stored_cognitive_packet_modified"),
        "reduction_ratio": receipt.get("reduction_ratio"),
    }


def _quality_trial_check() -> dict:
    plan = context_trial_manifest(["synthetic-model"], 1)
    return {
        "suite_version": plan.get("suite_version"),
        "planned_calls": plan.get("planned_calls"),
        "private_memory_reads": plan.get("private_memory_reads"),
        "memory_writes": plan.get("memory_writes"),
        "route_changes": plan.get("route_changes"),
        "automatic_promotion": plan.get("automatic_promotion"),
        "variants": plan.get("variants"),
    }


def _production_baseline_check() -> dict:
    report = summarise_production_baseline([])
    quality = report.get("answer_quality") or {}
    return {
        "mode": report.get("mode"),
        "empty_status": report.get("status"),
        "answer_quality_status": quality.get("status"),
        "score": quality.get("score"),
    }


def build_release_certification() -> dict:
    publication = _publication_and_delivery_check()
    failsafe = _runtime_failsafe_check()
    context = _context_budget_check()
    trials = _quality_trial_check()
    baseline = _production_baseline_check()

    checks = [
        _result(
            "publication_delivery_integrity",
            publication["publication_valid"]
            and publication["persistence_verified"]
            and publication["delivery_valid"],
            scope="synthetic_runtime",
            evidence=publication,
        ),
        _result(
            "bounded_cognition_failsafe",
            failsafe["degraded"]
            and failsafe["fallback_used"]
            and failsafe["diagnostic_bounded"]
            and failsafe["exception_message_hidden"],
            scope="synthetic_runtime",
            evidence=failsafe,
        ),
        _result(
            "adaptive_context_budget",
            context["mode"] == "lean"
            and context["marker_removed"]
            and context["required_context_preserved"]
            and context["rhee_evidence_modified"] is False
            and context["stored_cognitive_packet_modified"] is False,
            scope="synthetic_runtime",
            evidence=context,
        ),
        _result(
            "bounded_quality_trial_contract",
            trials["planned_calls"] == 8
            and trials["private_memory_reads"] is False
            and trials["memory_writes"] is False
            and trials["route_changes"] is False
            and trials["automatic_promotion"] is False
            and trials["variants"] == ["full", "budgeted"],
            scope="synthetic_manifest",
            evidence=trials,
        ),
        _result(
            "production_baseline_honesty",
            baseline["mode"] == "saved_production_operational_baseline"
            and baseline["empty_status"] == "no_data"
            and baseline["answer_quality_status"] == "not_scored"
            and baseline["score"] is None,
            scope="synthetic_runtime",
            evidence=baseline,
        ),
    ]
    verified = all(item["passed"] for item in checks)

    return {
        "version": VERSION,
        "layer": LAYER,
        "milestone": "project_l_100_layers",
        "status": "verified" if verified else "failed",
        "verified": verified,
        "core_version": CORE_VERSION,
        "controller_version": CONTROLLER_VERSION,
        "context_budget_version": CONTEXT_BUDGET_VERSION,
        "context_trial_version": CONTEXT_TRIAL_VERSION,
        "checks": checks,
        "claims": {
            "runtime_integrity_self_check": "verified" if verified else "failed",
            "production_deployment": "not_asserted_by_self_check",
            "live_model_quality": "not_asserted_by_self_check",
            "private_memory_recall_quality": "not_asserted_by_self_check",
            "phone_acceptance": "not_asserted_by_self_check",
            "human_conversation_review": "not_asserted_by_self_check",
        },
        "human_acceptance_required": [
            "live model quality",
            "private-memory recall quality",
            "conversation quality",
            "physical-phone UX",
        ],
        "limitations": [
            "This endpoint verifies deterministic runtime contracts only.",
            "A passing self-check is not a benchmark score or intelligence score.",
            "It does not prove Railway deployment state by itself.",
            "It does not replace live model, memory, browser or human acceptance testing.",
        ],
    }

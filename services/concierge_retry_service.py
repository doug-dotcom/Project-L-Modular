"""Durable Foundation Concierge retry/resume worker for Project L."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import httpx

from services.foundation_companion_service import (
    _foundation_url,
    _response_json,
    _rpc_data,
    _single_secret,
    delayed_synthesis_state,
    ensure_foundation_delegation,
    set_pending_concierge_job_status,
    store_delayed_synthesis_answer,
    store_delayed_synthesis_packet,
)


CLIENT_ID = "shine.companion"
MAX_RETRY_CAPABILITIES = 20
DEFAULT_RETRY_POLL_SECONDS = 30.0
MAX_LOCAL_INPUT_BYTES = 48 * 1024


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _uuid(value: Any) -> str:
    return str(UUID(str(value)))


def _client_token(db) -> str:
    return _single_secret(
        _rpc_data(db, "concierge_foundation_client_token_v1"),
        "foundation-client",
    )


def _post(
    *,
    db,
    path: str,
    body: dict,
    foundation_url: str | None,
    timeout_seconds: float,
    delegation_token: str | None = None,
    post_impl=None,
):
    headers = {
        "Content-Type": "application/json",
        "X-Shine-Client-Token": _client_token(db),
    }
    if delegation_token:
        headers["X-Shine-Delegation-Token"] = delegation_token
    post = post_impl or httpx.post
    return post(
        _foundation_url(foundation_url) + path,
        headers=headers,
        json=body,
        timeout=timeout_seconds,
        follow_redirects=False,
    )


def claim_foundation_retry(
    db,
    *,
    foundation_url: str | None = None,
    timeout_seconds: float = 12.0,
    post_impl=None,
) -> dict:
    try:
        response = _post(
            db=db,
            path="/v1/concierge/retry/claim",
            body={"clientId": CLIENT_ID},
            foundation_url=foundation_url,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
        )
        body = _response_json(response)
    except (httpx.HTTPError, RuntimeError):
        return {"status": "unavailable", "reason_code": "retry-claim-unavailable"}

    if response.status_code != 200 or body.get("status") != "ok":
        return {
            "status": str(body.get("status") or "unavailable"),
            "reason_code": str(body.get("reasonCode") or "retry-claim-failed"),
        }
    retry = body.get("retry")
    if not isinstance(retry, dict):
        return {"status": "unavailable", "reason_code": "retry-claim-invalid"}
    if retry.get("claimed") is not True:
        return {"status": "idle", "reason_code": "no-retry-due"}

    try:
        capability_ids = [str(item) for item in list(retry.get("capabilityIds") or [])]
        claimed = {
            "status": "claimed",
            "reason_code": "retry-claimed",
            "retry_job_id": _uuid(retry.get("retryJobId")),
            "request_id": _uuid(retry.get("requestId")),
            "owner_shine_id": _uuid(retry.get("ownerShineId")),
            "claim_token": _uuid(retry.get("claimToken")),
            "capability_ids": capability_ids,
            "attempt": int(retry.get("attempt") or 1),
            "max_attempts": int(retry.get("maxAttempts") or 1),
            "expires_at": retry.get("expiresAt"),
        }
    except (ValueError, TypeError):
        return {"status": "unavailable", "reason_code": "retry-claim-invalid"}

    if (
        not capability_ids
        or len(capability_ids) > MAX_RETRY_CAPABILITIES
        or len(set(capability_ids)) != len(capability_ids)
        or any(
            not capability_id
            or len(capability_id) > 128
            or any(
                ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-"
                for ch in capability_id
            )
            for capability_id in capability_ids
        )
    ):
        return {"status": "unavailable", "reason_code": "retry-claim-invalid"}
    return claimed


def _load_local_job(db, owner_id: str, request_id: str) -> dict | None:
    result = (
        db.table("companion_foundation_pending_jobs")
        .select(
            "job_id,user_id,link_request_id,purpose,capability_ids,inputs,"
            "source_conversation_id,source_message_id,request_text,status,"
            "cancellation_reason,superseded_by_request_id,cancelled_at"
        )
        .eq("job_id", request_id)
        .eq("user_id", owner_id)
        .limit(2)
        .execute()
    )
    rows = getattr(result, "data", None)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    return rows[0]


def _finish_remote_retry(
    db,
    claim: dict,
    *,
    outcome: str,
    reason_code: str,
    retry_after: str | None = None,
    foundation_url: str | None = None,
    timeout_seconds: float = 12.0,
    post_impl=None,
) -> dict:
    if outcome not in {"completed", "retry", "abandoned"}:
        raise ValueError("invalid retry outcome")
    envelope = {
        "retryFinish": "shine-foundation/concierge-retry-finish-v1",
        "schemaVersion": "1.0.0",
        "clientId": CLIENT_ID,
        "retryJobId": claim["retry_job_id"],
        "claimToken": claim["claim_token"],
        "outcome": outcome,
        "reasonCode": str(reason_code or "retry-finished")[:160],
    }
    if retry_after:
        envelope["retryAfter"] = retry_after
    try:
        response = _post(
            db=db,
            path="/v1/concierge/retry/finish",
            body=envelope,
            foundation_url=foundation_url,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
        )
        body = _response_json(response)
    except (httpx.HTTPError, RuntimeError):
        return {"status": "unavailable", "reason_code": "retry-finish-unavailable"}
    if response.status_code != 200 or body.get("status") != "ok":
        return {
            "status": str(body.get("status") or "unavailable"),
            "reason_code": str(body.get("reasonCode") or "retry-finish-failed"),
        }
    return {
        "status": "ok",
        "reason_code": "retry-finished",
        "retry": body.get("retry") if isinstance(body.get("retry"), dict) else {},
    }


def _emit_completion_event(
    db,
    *,
    job: dict,
    event_type: str,
    reason_code: str,
) -> None:
    if event_type not in {"retry-completed", "retry-abandoned"}:
        raise ValueError("invalid completion event type")
    owner_id = _uuid(job.get("user_id"))
    request_id = _uuid(job.get("job_id"))
    existing = (
        db.table("companion_concierge_completion_outbox")
        .select("event_id")
        .eq("user_id", owner_id)
        .eq("concierge_request_id", request_id)
        .eq("event_type", event_type)
        .limit(1)
        .execute()
    )
    rows = getattr(existing, "data", None)
    if isinstance(rows, list) and rows:
        return
    db.table("companion_concierge_completion_outbox").insert({
        "event_id": str(uuid4()),
        "user_id": owner_id,
        "concierge_request_id": request_id,
        "event_type": event_type,
        "summary_state": "ready-to-surface",
        "reason_code": str(reason_code or event_type)[:160],
        "capability_ids": list(job.get("capability_ids") or [])[:20],
        "source_conversation_id": job.get("source_conversation_id"),
        "source_message_id": job.get("source_message_id"),
        "expires_at": (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat().replace("+00:00", "Z"),
    }).execute()


def _local_inputs_for_claim(job: dict, claim: dict) -> dict | None:
    if str(job.get("status") or "") not in {"ready", "completed"}:
        return None
    local_capabilities = [str(item) for item in list(job.get("capability_ids") or [])]
    claimed = claim["capability_ids"]
    if any(capability_id not in local_capabilities for capability_id in claimed):
        return None
    inputs = job.get("inputs")
    if not isinstance(inputs, dict):
        return None
    selected = {}
    for capability_id in claimed:
        value = inputs.get(capability_id)
        if not isinstance(value, dict):
            return None
        selected[capability_id] = value
    try:
        size = len(
            json.dumps(
                selected,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    except Exception:
        return None
    if size > MAX_LOCAL_INPUT_BYTES:
        return None
    return selected


def _resume_foundation(
    db,
    claim: dict,
    job: dict,
    inputs: dict,
    *,
    foundation_url: str | None = None,
    timeout_seconds: float = 145.0,
    post_impl=None,
) -> dict:
    authority = ensure_foundation_delegation(
        db,
        claim["owner_shine_id"],
        foundation_url=foundation_url,
        timeout_seconds=min(timeout_seconds, 12.0),
        post_impl=post_impl,
    )
    if authority.get("status") != "active":
        return {
            "status": "authority-unavailable",
            "reason_code": str(
                authority.get("reason_code") or authority.get("status") or
                "foundation-authority-unavailable"
            ),
        }

    envelope = {
        "conciergeExecute": "shine-concierge/execute-v1",
        "schemaVersion": "1.0.0",
        "requestId": claim["request_id"],
        "clientId": CLIENT_ID,
        "inputs": inputs,
        "requestedAt": _iso_now(),
    }
    try:
        response = _post(
            db=db,
            path="/v1/concierge/resume",
            body=envelope,
            foundation_url=foundation_url,
            timeout_seconds=timeout_seconds,
            delegation_token=_single_secret(
                authority.get("delegation_token"),
                "foundation-delegation",
            ),
            post_impl=post_impl,
        )
        body = _response_json(response)
    except (httpx.HTTPError, RuntimeError):
        return {"status": "network-uncertain", "reason_code": "concierge-resume-unavailable"}

    return {
        "status": str(body.get("status") or "unavailable"),
        "reason_code": str(body.get("reasonCode") or "concierge-resume-unavailable"),
        "results": body.get("results") if isinstance(body.get("results"), list) else [],
        "retry": body.get("retry") if isinstance(body.get("retry"), dict) else None,
        "unavailable_capabilities": (
            body.get("unavailableCapabilities")
            if isinstance(body.get("unavailableCapabilities"), list)
            else []
        ),
        "synthesis_ready": body.get("synthesisReady") is True,
        "synthesis_must_disclose_partial": (
            body.get("synthesisMustDisclosePartial") is True
        ),
        "http_status": int(response.status_code),
    }


def _retry_after_from_resume(resume: dict) -> str | None:
    values = []
    for item in resume.get("unavailable_capabilities") or []:
        if isinstance(item, dict) and isinstance(item.get("retryAfter"), str):
            values.append(item["retryAfter"])
    return min(values) if values else None


def _resume_has_distinct_queued_retry(resume: dict, claim: dict) -> bool:
    retry = resume.get("retry")
    if not isinstance(retry, dict) or retry.get("queued") is not True:
        return False
    retry_job_id = str(retry.get("retryJobId") or "")
    return bool(retry_job_id and retry_job_id != claim["retry_job_id"])


def _completion_packet(claim: dict, resume: dict) -> dict:
    return {
        "version": "shine-concierge-delayed-result/v1",
        "request_id": claim["request_id"],
        "status": str(resume.get("status") or "completed"),
        "reason_code": str(
            resume.get("reason_code") or "concierge-resume-completed"
        ),
        "capability_ids": list(claim.get("capability_ids") or [])[:20],
        "results": list(resume.get("results") or [])[:20],
        "synthesis_ready": resume.get("synthesis_ready") is True,
        "synthesis_must_disclose_partial": (
            resume.get("synthesis_must_disclose_partial") is True
        ),
    }


def _cancellation_result(
    db,
    claim: dict,
    *,
    foundation_url: str | None = None,
    post_impl=None,
) -> dict | None:
    job = _load_local_job(
        db,
        claim["owner_shine_id"],
        claim["request_id"],
    )
    if job is None:
        return None
    state = str(job.get("status") or "")
    reason = str(
        job.get("cancellation_reason") or "concierge-request-cancelled"
    )[:160]
    superseded_by = str(job.get("superseded_by_request_id") or "") or None

    if state == "cancelling":
        return {
            "status": "cancelling",
            "reason_code": reason,
            "finish_status": "claim-held-for-cancellation",
            "superseded_by_request_id": superseded_by,
        }

    if state == "cancelled":
        finish = _finish_remote_retry(
            db,
            claim,
            outcome="abandoned",
            reason_code=reason,
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        return {
            "status": "cancelled",
            "reason_code": reason,
            "finish_status": finish.get("status"),
            "superseded_by_request_id": superseded_by,
        }

    return None


def run_concierge_retry_once(
    db,
    *,
    foundation_url: str | None = None,
    post_impl=None,
    synthesise=None,
) -> dict:
    claim = claim_foundation_retry(
        db,
        foundation_url=foundation_url,
        post_impl=post_impl,
    )
    if claim.get("status") != "claimed":
        return claim

    cancellation = _cancellation_result(
        db,
        claim,
        foundation_url=foundation_url,
        post_impl=post_impl,
    )
    if cancellation is not None:
        return cancellation

    job = _load_local_job(db, claim["owner_shine_id"], claim["request_id"])
    inputs = _local_inputs_for_claim(job, claim) if job else None
    if job is None or inputs is None:
        cancellation = _cancellation_result(
            db,
            claim,
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        if cancellation is not None:
            return cancellation

        finish = _finish_remote_retry(
            db,
            claim,
            outcome="abandoned",
            reason_code="companion-retry-context-missing",
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        if job:
            try:
                transitioned = set_pending_concierge_job_status(
                    db,
                    user_id=claim["owner_shine_id"],
                    job_id=claim["request_id"],
                    status="failed",
                )
                if not transitioned:
                    cancellation = _cancellation_result(
                        db,
                        claim,
                        foundation_url=foundation_url,
                        post_impl=post_impl,
                    )
                    if cancellation is not None:
                        return cancellation
                    raise RuntimeError("concierge-local-state-transition-rejected")
                _emit_completion_event(
                    db,
                    job=job,
                    event_type="retry-abandoned",
                    reason_code="companion-retry-context-missing",
                )
            except Exception:
                pass
        return {
            "status": "abandoned",
            "reason_code": "companion-retry-context-missing",
            "finish_status": finish.get("status"),
        }

    resume = _resume_foundation(
        db,
        claim,
        job,
        inputs,
        foundation_url=foundation_url,
        post_impl=post_impl,
    )
    status = resume.get("status")

    cancellation = _cancellation_result(
        db,
        claim,
        foundation_url=foundation_url,
        post_impl=post_impl,
    )
    if cancellation is not None:
        return cancellation

    if status == "completed":
        # Foundation checkpoints are now terminal specialist truth. Freeze that
        # exact packet privately before L generates any delayed user-facing prose.
        completion_packet = _completion_packet(claim, resume)
        packet_store = store_delayed_synthesis_packet(
            db,
            user_id=claim["owner_shine_id"],
            request_id=claim["request_id"],
            result_packet=completion_packet,
        )
        synthesis_state = delayed_synthesis_state(
            db,
            user_id=claim["owner_shine_id"],
            request_id=claim["request_id"],
        )

        answer_ready = (
            synthesis_state.get("synthesisStatus") == "ready"
            and isinstance(synthesis_state.get("finalAnswer"), str)
            and bool(synthesis_state.get("finalAnswer").strip())
        )
        synthesis_replayed = answer_ready

        if not answer_ready:
            request_text = str(
                synthesis_state.get("requestText")
                or job.get("request_text")
                or ""
            ).strip()
            if not request_text or not callable(synthesise):
                return {
                    "status": "synthesis-retry",
                    "reason_code": "delayed-synthesis-not-ready",
                    "packet_sha256": packet_store["packet_sha256"],
                    "finish_status": "claim-held-for-recovery",
                }

            try:
                generated = synthesise(request_text, completion_packet)
            except Exception:
                generated = {
                    "status": "unavailable",
                    "reason_code": "delayed-synthesis-generation-failed",
                }
            if (
                not isinstance(generated, dict)
                or generated.get("status") != "ready"
                or not isinstance(generated.get("reply"), str)
                or not generated["reply"].strip()
            ):
                return {
                    "status": "synthesis-retry",
                    "reason_code": str(
                        (generated or {}).get("reason_code")
                        if isinstance(generated, dict)
                        else "delayed-synthesis-generation-failed"
                    ),
                    "packet_sha256": packet_store["packet_sha256"],
                    "finish_status": "claim-held-for-recovery",
                }

            store_delayed_synthesis_answer(
                db,
                user_id=claim["owner_shine_id"],
                request_id=claim["request_id"],
                packet_sha256=packet_store["packet_sha256"],
                answer=generated["reply"],
                temporal_receipt=(
                    generated.get("temporal_receipt")
                    if isinstance(generated.get("temporal_receipt"), dict)
                    else None
                ),
                generated_at=str(generated.get("generated_at") or ""),
            )

        cancellation = _cancellation_result(
            db,
            claim,
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        if cancellation is not None:
            return cancellation

        # Only an answer-bound completion becomes surfaceable. This is written
        # before retry-finish; a lost finish acknowledgement can therefore replay
        # checkpoints and the already-hashed answer without another model call.
        transitioned = set_pending_concierge_job_status(
            db,
            user_id=claim["owner_shine_id"],
            job_id=claim["request_id"],
            status="completed",
        )
        if not transitioned:
            cancellation = _cancellation_result(
                db,
                claim,
                foundation_url=foundation_url,
                post_impl=post_impl,
            )
            if cancellation is not None:
                return cancellation
            return {
                "status": "unavailable",
                "reason_code": "concierge-local-state-transition-rejected",
                "finish_status": "claim-held-for-recovery",
            }
        _emit_completion_event(
            db,
            job=job,
            event_type="retry-completed",
            reason_code="concierge-resume-completed",
        )
        finish = _finish_remote_retry(
            db,
            claim,
            outcome="completed",
            reason_code="concierge-resume-completed",
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        return {
            "status": "completed",
            "reason_code": "concierge-resume-completed",
            "finish_status": finish.get("status"),
            "packet_sha256": packet_store["packet_sha256"],
            "synthesis_replayed": synthesis_replayed,
            "reused_count": sum(
                1 for row in resume.get("results") or []
                if isinstance(row, dict) and row.get("reused") is True
            ),
        }

    if status == "partial":
        distinct_retry = _resume_has_distinct_queued_retry(resume, claim)
        # During resume, Foundation's execution queue normally sees this very
        # claim as "already pending". That is not a next attempt. Only a distinct
        # newly queued retry lets us close the old lease as completed; otherwise
        # finish(outcome=retry) atomically creates the next attempt.
        finish = _finish_remote_retry(
            db,
            claim,
            outcome="completed" if distinct_retry else "retry",
            reason_code=(
                "concierge-resume-partial-requeued"
                if distinct_retry
                else "concierge-resume-partial-next-attempt"
            ),
            retry_after=None if distinct_retry else _retry_after_from_resume(resume),
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        return {
            "status": "partial",
            "reason_code": (
                "concierge-resume-partial-requeued"
                if distinct_retry
                else "concierge-resume-partial-next-attempt"
            ),
            "finish_status": finish.get("status"),
            "next_retry_scheduled": (
                distinct_retry or finish.get("status") == "ok"
            ),
            "reused_count": sum(
                1 for row in resume.get("results") or []
                if isinstance(row, dict) and row.get("reused") is True
            ),
        }

    if status in {"network-uncertain", "unavailable", "authority-unavailable"}:
        distinct_retry = _resume_has_distinct_queued_retry(resume, claim)
        finish = _finish_remote_retry(
            db,
            claim,
            outcome="completed" if distinct_retry else "retry",
            reason_code=str(resume.get("reason_code") or "concierge-resume-retry"),
            retry_after=None if distinct_retry else _retry_after_from_resume(resume),
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        return {
            "status": "retry",
            "reason_code": str(resume.get("reason_code") or "concierge-resume-retry"),
            "finish_status": finish.get("status"),
            "next_retry_scheduled": (
                distinct_retry or finish.get("status") == "ok"
            ),
        }

    transitioned = set_pending_concierge_job_status(
        db,
        user_id=claim["owner_shine_id"],
        job_id=claim["request_id"],
        status="failed",
    )
    if not transitioned:
        cancellation = _cancellation_result(
            db,
            claim,
            foundation_url=foundation_url,
            post_impl=post_impl,
        )
        if cancellation is not None:
            return cancellation
        return {
            "status": "unavailable",
            "reason_code": "concierge-local-state-transition-rejected",
            "finish_status": "claim-held-for-recovery",
        }
    _emit_completion_event(
        db,
        job=job,
        event_type="retry-abandoned",
        reason_code=str(
            resume.get("reason_code") or "concierge-resume-terminal-failure"
        ),
    )
    finish = _finish_remote_retry(
        db,
        claim,
        outcome="abandoned",
        reason_code=str(resume.get("reason_code") or "concierge-resume-terminal-failure"),
        foundation_url=foundation_url,
        post_impl=post_impl,
    )
    return {
        "status": "abandoned",
        "reason_code": str(
            resume.get("reason_code") or "concierge-resume-terminal-failure"
        ),
        "finish_status": finish.get("status"),
    }


class ConciergeRetryRunner:
    """Single bounded background consumer for Foundation retry jobs."""

    def __init__(
        self,
        db,
        *,
        poll_seconds: float = DEFAULT_RETRY_POLL_SECONDS,
        foundation_url: str | None = None,
        logger=None,
        synthesise=None,
    ):
        self.db = db
        self.poll_seconds = max(5.0, float(poll_seconds))
        self.foundation_url = foundation_url
        self.logger = logger
        self.synthesise = synthesise
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="l-concierge-retry",
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def _log(self, message: str):
        if callable(self.logger):
            try:
                self.logger(message)
            except Exception:
                pass

    def _loop(self):
        while not self.stop_event.is_set():
            delay = self.poll_seconds
            try:
                result = run_concierge_retry_once(
                    self.db,
                    foundation_url=self.foundation_url,
                    synthesise=self.synthesise,
                )
                status = str(result.get("status") or "unknown")
                if status not in {"idle", "unavailable"}:
                    self._log(
                        "CONCIERGE RETRY: "
                        f"status={status} | reason={result.get('reason_code', '')}"
                    )
                if status in {"completed", "partial", "abandoned"}:
                    delay = 1.0
            except Exception as exc:
                self._log(
                    "CONCIERGE RETRY ERROR: "
                    f"{type(exc).__name__}"
                )
            self.stop_event.wait(delay)

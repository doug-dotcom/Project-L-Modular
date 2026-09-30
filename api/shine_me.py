"""Owner-only context endpoint for the native Shine-Me companion."""

import json
import os
import re
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.cognition.shine_me_service import (
    answer_from_shine_me_context,
    prepare_shine_me_context,
    shine_me_binding_status,
)


class ContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class CorrectionRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    expected_source: str = Field(min_length=1, max_length=160)
    issue_kind: str = Field(pattern="^(wrong|incomplete)$")
    proposed_correction: str = Field(min_length=1, max_length=2000)


class OwnerStateRequest(BaseModel):
    state: dict
    expected_revision: int = Field(ge=0, le=2_147_483_647)


_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STATE_KEYS = {"mood", "moodNote", "goals", "routines", "history", "journal", "dailyCheckins", "lastDay"}


def _clean_day(value, *, optional=True):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _DAY_RE.fullmatch(value):
        raise ValueError("Invalid Shine-Me state date.")
    return value


def _clean_text(value, maximum):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("Invalid Shine-Me state text.")
    return value


def _clean_item_list(value, *, maximum=100):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("Invalid Shine-Me state list.")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Invalid Shine-Me state item.")
        text = _clean_text(item.get("text"), 120).strip()
        if not text:
            raise ValueError("Shine-Me state item text cannot be blank.")
        rows.append({
            "text": text,
            "done": bool(item.get("done", False)),
            "completedOn": _clean_day(item.get("completedOn"), optional=True),
        })
    return rows


def _clean_history(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 30:
        raise ValueError("Invalid Shine-Me history.")
    history = {}
    for day, entry in value.items():
        key = _clean_day(day, optional=False)
        if not isinstance(entry, dict):
            raise ValueError("Invalid Shine-Me history entry.")
        mood = entry.get("mood")
        if mood is not None and (not isinstance(mood, int) or not 0 <= mood <= 4):
            raise ValueError("Invalid Shine-Me mood history.")
        def bounded_count(name):
            count = entry.get(name, 0)
            if not isinstance(count, int) or not 0 <= count <= 1000:
                raise ValueError("Invalid Shine-Me history count.")
            return count
        touched = entry.get("touchedAt")
        if touched is not None and (not isinstance(touched, str) or len(touched) > 64):
            raise ValueError("Invalid Shine-Me history timestamp.")
        history[key] = {
            "mood": mood,
            "goalCompleted": bounded_count("goalCompleted"),
            "goalDoneTotal": bounded_count("goalDoneTotal"),
            "goalTotal": bounded_count("goalTotal"),
            "routineCompleted": bounded_count("routineCompleted"),
            "routineTotal": bounded_count("routineTotal"),
            "touchedAt": touched,
        }
    return history


def _clean_daily_checkins(value):
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 30:
        raise ValueError("Invalid Shine-Me daily check-ins.")
    rows = {}
    for day, entry in value.items():
        key = _clean_day(day, optional=False)
        if not isinstance(entry, dict):
            raise ValueError("Invalid Shine-Me daily check-in.")
        score = entry.get("score")
        sleep = entry.get("sleep")
        for name, number in (("score", score), ("sleep", sleep)):
            if number is not None and (
                not isinstance(number, (int, float))
                or isinstance(number, bool)
                or number < 0
                or number > 10
            ):
                raise ValueError(f"Invalid Shine-Me daily {name}.")
        mood = entry.get("mood")
        if mood is not None and (not isinstance(mood, int) or isinstance(mood, bool) or not 0 <= mood <= 4):
            raise ValueError("Invalid Shine-Me daily mood.")
        updated_at = entry.get("updatedAt")
        if updated_at is not None and (
            not isinstance(updated_at, str) or len(updated_at) > 64
        ):
            raise ValueError("Invalid Shine-Me daily check-in timestamp.")
        rows[key] = {
            "mood": mood,
            "feeling1": _clean_text(entry.get("feeling1"), 40).strip(),
            "feeling2": _clean_text(entry.get("feeling2"), 40).strip(),
            "score": score,
            "sleep": sleep,
            "gratitude": _clean_text(entry.get("gratitude"), 500),
            "challenge": _clean_text(entry.get("challenge"), 500),
            "intention": _clean_text(entry.get("intention"), 500),
            "note": _clean_text(entry.get("note"), 1000),
            "updatedAt": updated_at,
        }
    return rows


def _clean_journal(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError("Invalid Shine-Me journal.")
    rows = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("Invalid Shine-Me journal entry.")
        created = entry.get("createdAt")
        if not isinstance(created, str) or not created or len(created) > 64:
            raise ValueError("Invalid Shine-Me journal timestamp.")
        rows.append({
            "createdAt": created,
            "reflection": _clean_text(entry.get("reflection"), 1500),
            "gratitude": _clean_text(entry.get("gratitude"), 600),
            "next": _clean_text(entry.get("next"), 600),
        })
    return rows


def _clean_owner_state(raw):
    if not isinstance(raw, dict) or set(raw) - _STATE_KEYS:
        raise ValueError("Unsupported Shine-Me state fields.")
    mood = raw.get("mood")
    if mood is not None and (not isinstance(mood, int) or not 0 <= mood <= 4):
        raise ValueError("Invalid Shine-Me mood.")
    clean = {
        "mood": mood,
        "moodNote": _clean_text(raw.get("moodNote"), 500),
        "goals": _clean_item_list(raw.get("goals")),
        "routines": _clean_item_list(raw.get("routines")),
        "history": _clean_history(raw.get("history")),
        "journal": _clean_journal(raw.get("journal")),
        "dailyCheckins": _clean_daily_checkins(raw.get("dailyCheckins")),
        "lastDay": _clean_day(raw.get("lastDay"), optional=True),
    }
    if len(json.dumps(clean, separators=(",", ":"), ensure_ascii=False)) > 64_000:
        raise ValueError("Shine-Me state is too large.")
    return clean


def routes(
    retrieve, cognize, check_freshness,
    save_correction: Callable[[dict], object] | None = None,
    list_corrections: Callable[[str], object] | None = None,
    load_owner_state: Callable[[str], object] | None = None,
    insert_owner_state: Callable[[dict], object] | None = None,
    update_owner_state: Callable[[str, int, dict], object] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["shine-me"])

    def approved_context(payload: ContextRequest, request: Request) -> dict:
        # /shine-me/context is protected by the server's account middleware.
        # Require the account state as a second boundary: a recovery token is
        # never an identity and user_id is never accepted in the request body.
        try:
            return prepare_shine_me_context(
                query=payload.query,
                verified_account=getattr(request.state, "account", None),
                configured_owner_id=os.getenv("PROJECT_L_OWNER_ID", ""),
                configured_memory_owner_id=os.getenv("L_MEMORY_OWNER_ID", ""),
                retrieve=retrieve,
                cognize=cognize,
                check_freshness=check_freshness,
            )
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot access Shine-Me memory.") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, "Shine-Me context is temporarily unavailable.") from exc

    @router.get("/shine-me/binding")
    def binding(request: Request) -> dict:
        try:
            return shine_me_binding_status(
                verified_account=getattr(request.state, "account", None),
                configured_owner_id=os.getenv("PROJECT_L_OWNER_ID", ""),
                configured_memory_owner_id=os.getenv("L_MEMORY_OWNER_ID", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot access Shine-Me memory.") from exc
        except RuntimeError as exc:
            raise HTTPException(503, "Shine-Me owner binding is unavailable.") from exc


    @router.get("/shine-me/state")
    def owner_state(request: Request) -> dict:
        binding(request)
        if not os.getenv("SUPABASE_SERVICE_ROLE_KEY") or load_owner_state is None:
            raise HTTPException(503, "Shine-Me account sync is temporarily unavailable.")
        owner_id = str(os.getenv("PROJECT_L_OWNER_ID") or "").strip()
        try:
            result = load_owner_state(owner_id)
            rows = getattr(result, "data", None)
            if not isinstance(rows, list):
                raise RuntimeError("Invalid state result")
            if not rows:
                return {"status": "empty", "state": None, "revision": 0, "updated_at": None}
            if len(rows) != 1 or rows[0].get("owner_id") != owner_id:
                raise RuntimeError("State owner mismatch")
            row = rows[0]
            return {
                "status": "synced",
                "state": _clean_owner_state(row.get("state") or {}),
                "revision": int(row.get("revision") or 0),
                "updated_at": row.get("updated_at"),
            }
        except ValueError as exc:
            raise HTTPException(503, "Stored Shine-Me state is invalid.") from exc
        except Exception as exc:
            raise HTTPException(503, "Shine-Me account state could not be loaded.") from exc

    @router.put("/shine-me/state")
    def save_owner_state(payload: OwnerStateRequest, request: Request) -> dict:
        binding(request)
        if (
            not os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or load_owner_state is None
            or insert_owner_state is None
            or update_owner_state is None
        ):
            raise HTTPException(503, "Shine-Me account sync is temporarily unavailable.")
        owner_id = str(os.getenv("PROJECT_L_OWNER_ID") or "").strip()
        try:
            clean_state = _clean_owner_state(payload.state)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        now = datetime.now(timezone.utc).isoformat()
        next_revision = payload.expected_revision + 1
        row = {
            "owner_id": owner_id,
            "state": clean_state,
            "revision": next_revision,
            "updated_at": now,
        }
        try:
            if payload.expected_revision == 0:
                current = load_owner_state(owner_id)
                existing = getattr(current, "data", None)
                if not isinstance(existing, list):
                    raise RuntimeError("Invalid state result")
                if existing:
                    raise HTTPException(409, "Shine-Me state changed on another device.")
                saved = insert_owner_state(row)
            else:
                saved = update_owner_state(owner_id, payload.expected_revision, row)

            rows = getattr(saved, "data", None)
            if not isinstance(rows, list) or len(rows) != 1:
                raise HTTPException(409, "Shine-Me state changed on another device.")
            stored = rows[0]
            if (
                stored.get("owner_id") != owner_id
                or int(stored.get("revision") or 0) != next_revision
            ):
                raise RuntimeError("Invalid state receipt")
            return {
                "status": "synced",
                "revision": next_revision,
                "updated_at": stored.get("updated_at") or now,
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Shine-Me account state could not be saved.") from exc

    @router.post("/shine-me/context")
    def context(payload: ContextRequest, request: Request) -> dict:
        return approved_context(payload, request)

    @router.post("/shine-me/ask")
    def ask(payload: ContextRequest, request: Request) -> dict:
        return answer_from_shine_me_context(approved_context(payload, request))

    @router.post("/shine-me/corrections")
    def submit_correction(payload: CorrectionRequest, request: Request) -> dict:
        # Recheck the verified owner and publication gates at submission time.
        # Browser-supplied source text is only an expected match, never authority.
        context = approved_context(ContextRequest(query=payload.query), request)
        answer = answer_from_shine_me_context(context)
        evidence = answer.get("evidence") or []
        if not evidence or evidence[0].get("source") != payload.expected_source:
            raise HTTPException(409, "The sourced answer changed. Ask again before submitting.")
        if not os.getenv("SUPABASE_SERVICE_ROLE_KEY") or save_correction is None:
            raise HTTPException(503, "Correction review is temporarily unavailable.")
        owner_id = str(os.getenv("PROJECT_L_OWNER_ID") or "").strip()
        row = {
            "owner_id": owner_id,
            "question": payload.query.strip(),
            "source": evidence[0]["source"],
            "provenance": evidence[0].get("provenance", "unknown"),
            "original_reply": answer["reply"],
            "issue_kind": payload.issue_kind,
            "proposed_correction": payload.proposed_correction.strip(),
        }
        if not row["proposed_correction"]:
            raise HTTPException(400, "Correction cannot be blank.")
        try:
            saved = save_correction(row)
            data = getattr(saved, "data", None)
            if not isinstance(data, list) or len(data) != 1 or not data[0].get("id"):
                raise RuntimeError("Correction receipt missing")
            return {"status": "pending_review", "id": str(data[0]["id"])}
        except Exception as exc:
            raise HTTPException(503, "Correction could not be saved for review.") from exc

    @router.get("/shine-me/corrections")
    def corrections(request: Request) -> dict:
        # The account middleware authenticates first; require the owner binding
        # again before any database read. The storage callback filters by owner.
        binding(request)
        if not os.getenv("SUPABASE_SERVICE_ROLE_KEY") or list_corrections is None:
            raise HTTPException(503, "Correction review is temporarily unavailable.")
        owner_id = str(os.getenv("PROJECT_L_OWNER_ID") or "").strip()
        try:
            result = list_corrections(owner_id)
            rows = getattr(result, "data", None)
            if not isinstance(rows, list):
                raise RuntimeError("Invalid review result")
            fields = ("id", "question", "source", "provenance", "issue_kind",
                      "proposed_correction", "status", "created_at")
            if any(not isinstance(row, dict) or row.get("owner_id") != owner_id
                   for row in rows):
                raise RuntimeError("Review owner mismatch")
            return {"items": [{key: row.get(key) for key in fields} for row in rows]}
        except Exception as exc:
            raise HTTPException(503, "Corrections could not be loaded.") from exc

    return router

"""Deterministic capability routing. Services do not become L personalities."""

from __future__ import annotations


def _normalise(message: str) -> str:
    return str(message or "").strip().lower()


def _personal_reflection(text: str) -> bool:
    return any(signal in text for signal in (
        "my journey", "how do i feel", "what do you think about me", "my trauma",
        "my recovery", "my spirituality", "my emotions", "my relationship",
    ))


def _run(capability: str, handler, message: str) -> dict:
    try:
        reply = handler(message)
        return {"handled": True, "capability": capability, "reply": reply, "status": "ok"}
    except Exception as exc:
        return {
            "handled": True,
            "capability": capability,
            "reply": f"{capability.replace('_', ' ').title()} service error: {exc}",
            "status": "error",
        }


def route_capability(message: str) -> dict:
    text = _normalise(message)

    from services.google_workspace_service import (
        calendar_summary,
        classify_google_capability,
        gmail_summary,
        tasks_result,
    )
    google_capability = classify_google_capability(message)
    google_handlers = {
        "gmail": gmail_summary,
        "calendar": calendar_summary,
        "tasks": tasks_result,
    }
    if google_capability:
        return _run(google_capability, google_handlers[google_capability], message)

    finance_data_action = any(signal in text for signal in (
        "uploaded transactions", "transactions csv", "bank statement csv",
        "review my transactions", "analyse my transactions", "analyze my transactions",
    ))
    if finance_data_action:
        from agents.fiona import fiona
        if fiona.should_handle(text):
            return _run("financial_intelligence", fiona.handle_finance_request, message)

    from services.external_research_service import research, should_handle
    if should_handle(message) and not _personal_reflection(text):
        try:
            return {
                "handled": True,
                "capability": "external_research",
                "reply": research(message),
                "status": "ok",
            }
        except Exception as exc:
            return {
                "handled": True,
                "capability": "external_research",
                "reply": f"External research service error: {exc}",
                "status": "error",
            }

    return {"handled": False, "capability": "l_core", "reply": "", "status": "not_required"}

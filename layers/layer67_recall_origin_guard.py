"""Layer 67 — Recall origin guard.

Deep Recall is a deliberately explicit user contract. Internal recall machinery
may rewrite or broaden a query, but that derived wording must never be able to
promote a bounded lookup into a full-corpus Deep Recall scan.

A ContextVar is used rather than a module boolean so concurrent requests keep
their own origin state. Retrieval layers can mark recursive/internal passes and
Deep Recall can fail closed for those passes without changing ordinary recall.
"""
from contextvars import ContextVar


def install(rhee):
    existing = getattr(rhee, "_project_l_internal_recall_pass", None)
    if existing is None:
        rhee._project_l_internal_recall_pass = ContextVar(
            "project_l_internal_recall_pass",
            default=False,
        )

"""Hotfix — preserve completed recall evidence when target latency is exceeded.

The retrieval budget is a latency target, not a validity boundary. Broad recall
now performs bounded escalation/coverage passes, so a completed query can take
longer than the original 45s target. Do not discard evidence solely for being
late; record the timing separately and let downstream confidence/coverage logic
decide how strongly to answer.
"""


def install(rhee):
    previous_build_context = rhee.build_context

    def build_context(*args, **kwargs):
        receipt = kwargs.get("receipt_out")
        context = previous_build_context(*args, **kwargs)
        if isinstance(receipt, dict) and receipt.get("status") == "budget_exceeded":
            # build_context has already completed at this point. Preserve its
            # evidence and expose lateness as metadata rather than a hard error.
            receipt["budget_exceeded"] = True
            receipt["timing_status"] = "late_bounded_result"
            receipt["status"] = "checked"
        return context

    rhee.build_context = build_context

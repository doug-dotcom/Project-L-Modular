"""Layer 9 — evidence authority and conflict guardrails.

Recall can surface Doug-authored records, later corrections, promoted memories,
and old assistant summaries together. This layer makes source authority explicit
before answer generation. It does not decide disputed facts by itself; it tells
the answer model which evidence may override which and preserves conflicts.
"""


def install(rhee):
    previous_packet = rhee.build_context_packet

    def authority_rank(item):
        authority = item.get("authority")
        authority = authority if isinstance(authority, dict) else {}
        governed_class = rhee.safe_text(authority.get("class")).lower()
        precedence = authority.get("precedence")
        try:
            governed_precedence = int(precedence)
        except (TypeError, ValueError):
            governed_precedence = None

        # Owner-scoped v2 authority is the source of truth when present.
        # Higher precedence means stronger authority; map it into the existing
        # lower-is-stronger sort contract while retaining a deterministic tie.
        if item.get("provenance") == "owner_scoped_v2" and governed_precedence is not None:
            return (0, -governed_precedence, governed_class)

        role = rhee.safe_text(item.get("role")).lower()
        source = rhee.safe_text(item.get("source")).lower()
        # Compatibility fallback for evidence not yet carrying governed v2
        # metadata. It must never outrank a governed item merely by source name.
        if role == "user":
            return (1, 0, "legacy-user")
        if role not in {"assistant", "model"} and (
            source.startswith("memory_") or source.startswith("identity_anchors")
            or source.startswith("episodic_memories")
        ):
            return (2, 0, "legacy-promoted")
        if role in {"assistant", "model"}:
            return (4, 0, "legacy-assistant")
        return (3, 0, "legacy-other")

    def packet(query):
        result = previous_packet(query)
        if (result.get("recall_plan") or {}).get("status") == "needs_clarification":
            return result

        evidence = list(result.get("evidence") or [])
        if not evidence:
            return result

        ranked = sorted(enumerate(evidence), key=lambda pair: (authority_rank(pair[1]), pair[0]))
        ordered = [item for _, item in ranked]
        counts = {"user_primary": 0, "canonical_or_promoted": 0, "other": 0, "assistant_secondary": 0}
        for item in ordered:
            rank = authority_rank(item)
            authority = item.get("authority")
            authority = authority if isinstance(authority, dict) else {}
            authority_class = rhee.safe_text(authority.get("class")).lower()
            if authority_class == "direct_user_promoted_memory" or rank[0] == 1:
                counts["user_primary"] += 1
            elif rank[0] in {0, 2}:
                counts["canonical_or_promoted"] += 1
            elif rank[0] == 4:
                counts["assistant_secondary"] += 1
            else:
                counts["other"] += 1

        policy = """
RHEE EVIDENCE AUTHORITY REVIEW
- Doug-authored USER records are primary evidence.
- A later explicit Doug correction supersedes an older conflicting Doug statement when the correction is clearly about the same fact.
- Canonical/promoted memory may organise primary evidence but must not override a conflicting Doug-authored record without provenance supporting the change.
- ASSISTANT/model-generated summaries are secondary evidence and must never override Doug-authored evidence.
- If two credible primary records genuinely conflict and no clear correction resolves them, report the conflict/uncertainty rather than silently choosing one.
- Do not turn interpretation, inference, or an assistant's old wording into biography merely because it was retrieved.
""".strip()

        context = rhee.safe_text(result.get("context"))
        if policy not in context:
            context = policy + "\n\n" + context

        output = dict(result)
        output["evidence"] = ordered
        output["context"] = context
        output["context_size"] = len(context)
        receipt = dict(output.get("recall_plan") or {})
        receipt.update({
            "authority_review": "applied",
            "authority_contract": "owner-scoped-v2-precedence-first",
            "authority_counts": counts,
            "conflict_policy": "preserve_primary_conflicts_and_prefer_explicit_user_corrections",
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet

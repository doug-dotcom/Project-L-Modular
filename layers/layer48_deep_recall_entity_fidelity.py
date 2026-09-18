"""Layer 48 — Deep Recall exact-name / entity fidelity guard.

A long personal archive can contain people, employers, schools and places with
similar names. Retrieval expansion, aliases and broad timelines must not cause L
to merge distinct entities or silently substitute a related entity for the one
Doug asked about.

This final composition guard preserves exact named-entity fidelity. Alias links
remain useful retrieval leads only when source evidence explicitly supports the
connection. Ordinary Recall is unchanged.
"""
import re
from collections import Counter

NAME_RE = re.compile(
    r"\b(?:[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3}|[A-Z]{2,8})\b"
)

STOP_NAMES = {
    "Deep Recall", "Project", "Source", "Doug", "USER", "ASSISTANT",
    "SOURCE", "ROLE", "CREATED", "WINDOW", "YES",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def names(text):
        found = []
        seen = set()
        for name in NAME_RE.findall(rhee.safe_text(text)):
            cleaned = name.strip()
            if cleaned in STOP_NAMES or cleaned in seen:
                continue
            found.append(cleaned); seen.add(cleaned)
        return found

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        query_names = names(query)
        evidence = list(result.get("evidence") or [])
        evidence_names = Counter()
        for item in evidence:
            for name in names(item.get("quote_source")):
                evidence_names[name] += 1

        plan = dict(result.get("recall_plan") or {})
        alias_links = list(plan.get("deep_recall_alias_links_followed") or [])

        output = dict(result)
        plan.update({
            "deep_recall_entity_fidelity": "applied",
            "deep_recall_query_named_entities": query_names,
            "deep_recall_evidence_named_entity_preview": [
                {"name": name, "count": count}
                for name, count in evidence_names.most_common(50)
            ],
            "deep_recall_entity_alias_links_available": alias_links[:20],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL EXACT-NAME / ENTITY-FIDELITY GUARD",
            "Named people, employers, businesses, schools, organisations and places must remain distinct unless retrieved evidence explicitly establishes that two labels refer to the same entity.",
            "Do not merge similar names, family members, employers, schools, locations or organisations merely because they appear in the same period or semantic neighbourhood.",
            "If Doug names a specific entity in the request, evidence about an adjacent or similarly named entity does not satisfy that part of the question.",
            "Evidence-discovered aliases are retrieval leads. Use an alias as an identity fact only when the source evidence supports that linkage.",
            "Relationship labels such as Mum, Dad, sponsor, partner, boss or friend are context-dependent; do not permanently bind them to a person unless the evidence for the relevant period establishes the relationship.",
            "When identity is ambiguous, preserve the exact source wording and state the ambiguity instead of choosing the most plausible person/entity.",
        ]
        if query_names:
            lines.append("Exact named entities detected in Doug's request: " + ", ".join(query_names))

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer49_deep_recall_route_ledger import install as install_route_ledger
    install_route_ledger(rhee)

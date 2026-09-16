"""Layer 13 — conversational recall-depth escalation.

Normal recall is quick. A bare follow-up "deep recall" reuses the most recent
recall query in this running conversation service and applies the full deep
recall contract. Explicit deep-recall queries remain unchanged.
"""
import re


def install(rhee):
    previous_packet = rhee.build_context_packet
    state = {"last_recall_query": ""}

    def bare_deep(query):
        text = rhee.safe_text(query).lower().strip()
        text = re.sub(r"[.!?]+$", "", text).strip()
        return bool(re.fullmatch(
            r"(?:please\s+)?(?:deep\s+recall|dig\s+deeper|look\s+deeper|go\s+deeper)"
            r"(?:\s+(?:please|that|it|this|more))?", text))

    def packet(query):
        if bare_deep(query):
            inherited = state.get("last_recall_query", "")
            if inherited:
                result = previous_packet("deep recall " + inherited)
                output = dict(result)
                receipt = dict(output.get("recall_plan") or {})
                receipt.update({
                    "deep_recall_followup": "inherited_previous_recall",
                    "deep_recall_inherited_query": inherited[:500],
                })
                output["recall_plan"] = receipt
                context = rhee.safe_text(output.get("context"))
                output["context"] = (
                    "DEEP RECALL FOLLOW-UP CONTRACT\n"
                    "The current command escalates the immediately preceding recall subject.\n\n"
                    + context
                )
                output["context_size"] = len(output["context"])
                output["deep_recall"] = True
                return output
            return previous_packet(query)

        result = previous_packet(query)
        if rhee.recall_requested(query):
            state["last_recall_query"] = rhee.safe_text(query)
        return result

    rhee.build_context_packet = packet

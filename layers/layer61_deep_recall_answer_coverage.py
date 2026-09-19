"""Layer 61 — Deep Recall final answer coverage enforcement.

The schooling A/B test retrieved later school stages but the final answer omitted
them while claiming the chronology was clear. Retrieval coverage and answer
coverage are different problems: evidence can be present yet disappear during
composition.

This layer builds a compact presentation checklist from explicit question parts,
final coverage state, dated/transition evidence and repeated named clues. It
requires every evidence-supported requested stage to appear in the final answer
or be explicitly marked as omitted for a stated evidentiary reason. It does not
invent stages or force thin material into the answer. Ordinary Recall is
unchanged.
"""
import re
from collections import Counter

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
GRADE_RE = re.compile(r"\b(?:grade|year)\s*(?:[1-9]|1[0-2])\b", re.I)
STAGE_RE = re.compile(
    r"\b(?:primary school|high school|school|army|university|college|"
    r"personal banker|financial planner|publican|owner|manager|"
    r"grade\s*(?:[1-9]|1[0-2])|year\s*(?:[1-9]|1[0-2]))\b",
    re.I,
)
PROPER_RE = re.compile(
    r"\b[A-Z][A-Za-z&.'-]{2,}(?:\s+[A-Z][A-Za-z&.'-]{2,}){0,3}\b"
)

STOP = {
    "Deep Recall", "Doug", "Source", "Project", "The", "This", "That", "My",
    "Australian Army", "Source Memory", "Source Raw",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})
        question_parts = list(plan.get("deep_recall_question_parts") or [])
        represented_parts = list(plan.get("deep_recall_final_represented_parts") or [])
        thin_parts = list(plan.get("deep_recall_final_thin_parts") or [])

        stage_counts = Counter()
        stage_sources = {}
        year_counts = Counter()
        grade_counts = Counter()

        for item in evidence:
            text = rhee.safe_text(item.get("quote_source"))
            source = rhee.safe_text(item.get("source"))

            for stage in STAGE_RE.findall(text):
                key = re.sub(r"\s+", " ", stage.strip())
                stage_counts[key] += 1
                stage_sources.setdefault(key, []).append(source)

            for grade in GRADE_RE.findall(text):
                key = re.sub(r"\s+", " ", grade.strip())
                grade_counts[key] += 1

            for year in set(YEAR_RE.findall(text)):
                year_counts[year] += 1

            # Proper names are useful only when repeated; they are candidate
            # presentation anchors, not automatically stages.
            for name in PROPER_RE.findall(text):
                name = name.strip()
                if name in STOP:
                    continue
                stage_counts[name] += 1
                stage_sources.setdefault(name, []).append(source)

        anchors = []
        for label, count in stage_counts.most_common(80):
            if count < 2:
                continue
            anchors.append({
                "label": label,
                "count": count,
                "sources": list(dict.fromkeys(stage_sources.get(label, [])))[:6],
            })

        output = dict(result)
        plan.update({
            "deep_recall_final_answer_coverage_enforcement": "applied",
            "deep_recall_presentation_question_parts": question_parts,
            "deep_recall_presentation_represented_parts": represented_parts,
            "deep_recall_presentation_thin_parts": thin_parts,
            "deep_recall_presentation_stage_anchors": anchors[:40],
            "deep_recall_presentation_years": sorted(year_counts, key=int)[:80],
            "deep_recall_presentation_grades": dict(grade_counts),
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL FINAL ANSWER-COVERAGE ENFORCEMENT",
            f"Requested parts={len(question_parts)}; final represented parts={len(represented_parts)}; final thin parts={len(thin_parts)}; repeated stage/entity anchors={len(anchors)}.",
            "Retrieval coverage is not enough: the FINAL USER-FACING ANSWER must actually present the evidence-supported requested stages and components.",
            "Before finishing, compare the drafted answer against the requested parts and the supported stage anchors in this completed packet.",
            "If a requested component is REPRESENTED by evidence, do not silently omit it merely to shorten or smooth the answer.",
            "For a chronological request, preserve each material evidence-supported stage in sequence. Do not jump from primary school to a closing interpretation when later school stages are present in the evidence.",
            "If evidence supports a stage but an exact date/name/detail is thin, include the supported stage and qualify only the uncertain detail rather than dropping the entire stage.",
            "If a stage is genuinely irrelevant to Doug's current question, it may be omitted; relevance to the current question remains controlling.",
            "Do not fill a checklist item with boilerplate such as 'I couldn't verify...' in place of supported content. Either present the supported evidence or identify the precise remaining gap once.",
            "Before ending the response, perform a silent presentation check: every material requested part is either ANSWERED from evidence, explicitly QUALIFIED as a candidate/partial result, or named once as a genuine remaining GAP.",
            "Do not expose this checklist or internal counters unless Doug asks for debugging details.",
        ]
        if anchors:
            lines.append(
                "Repeated stage/entity anchors for silent presentation review: " +
                "; ".join(f"{a['label']} x{a['count']}" for a in anchors[:25])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

# =====================================================
# ROOT PATH
# =====================================================

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# =====================================================
# IMPORTS
# =====================================================

from typing import Dict

from agents.frank.smart_routing import (
    route_query
)

from agents.frank.memory_first_search import (
    memory_first_search
)

from agents.frank.research_memory_retriever import (
    retrieve_research_memory
)

from agents.frank.internal_answer_engine import (
    generate_internal_answer
)

from agents.frank.external_verification_engine import (
    verify_answer
)

from agents.frank.executive_report import (
    generate_executive_report
)

from agents.frank.research_dashboard import (
    build_research_dashboard
)

from agents.connie.knowledge_recall import (
    recall_knowledge
)

from agents.connie.pattern_recall import (
    recall_patterns
)

from agents.connie.wisdom_recall import (
    recall_wisdom
)

from agents.connie.intuition_recall import (
    recall_intuition
)

from agents.connie.contradiction_detector import (
    detect_contradictions
)

from agents.frank.contradiction_hunter import (
    hunt_contradictions
)

from agents.frank.pattern_forecasting import (
    forecast_patterns
)

from agents.frank.research_brain_v2 import (
    run_research_brain_v2
)

from agents.connie.project_l_research_model import (
    build_project_l_research_model
)

from agents.connie.connie_export import (
    export_corpus
)

from agents.connie.training_dataset import (
    build_training_dataset
)

from agents.connie.lora_preparation import (
    prepare_lora_dataset
)

from agents.connie.lora_training import (
    run_lora_training
)

from agents.connie.model_evaluation import (
    evaluate_model
)

from agents.connie.local_llama_setup import (
    check_local_llama_setup
)

from agents.connie.corpus_import import (
    import_corpus
)

from agents.connie.lora_training import (
    run_lora_training
)

from agents.connie.model_evaluation import (
    evaluate_model
)

from agents.connie.local_llama_setup import (
    check_local_llama_setup
)

from agents.connie.corpus_import import (
    import_corpus
)

from agents.connie.connie_export import (
    export_corpus
)

from agents.connie.training_dataset import (
    build_training_dataset
)

from agents.connie.lora_preparation import (
    prepare_lora_dataset
)

from agents.connie.lora_training import (
    run_lora_training
)

from agents.connie.model_evaluation import (
    evaluate_model
)

from agents.connie.local_llama_setup import (
    check_local_llama_setup
)

from agents.connie.corpus_import import (
    import_corpus
)

from agents.connie.lora_training import (
    run_lora_training
)

from agents.connie.model_evaluation import (
    evaluate_model
)

from agents.connie.local_llama_setup import (
    check_local_llama_setup
)

from agents.connie.corpus_import import (
    import_corpus
)

# =====================================================
# RESEARCH BRAIN
# =====================================================

def run_research_brain(
    query: str,
    memory_records: list,
    research_records: list
) -> Dict:

    route = route_query(
        query
    )

    memory = memory_first_search(
        query,
        memory_records
    )

    research = retrieve_research_memory(
        query,
        research_records
    )

    answer = generate_internal_answer(
        query,
        research["matches"]
    )

    verification = verify_answer(
        answer["answer"],
        answer["answer"]
    )

    report = generate_executive_report(
        research_count = research["match_count"],
        insight_count = 1,
        prediction_count = 0
    )

    dashboard = build_research_dashboard(
        research_count = research["match_count"],
        pattern_count = memory["match_count"],
        insight_count = 1,
        prediction_count = 0
    )

    knowledge = recall_knowledge(
        query,
        [
            {
                "content":
                    answer["answer"]
            }
        ]
    )

    patterns = recall_patterns(
        query,
        [
            {
                "pattern":
                    query
            }
        ]
    )

    wisdom = recall_wisdom(
        query,
        [
            {
                "wisdom":
                    query
            }
        ]
    )

    intuition = recall_intuition(
        query,
        [
            {
                "prediction":
                    query
            }
        ]
    )

    brain_v2 = run_research_brain_v2(
        query,
        memory_records
    )

    research_model = build_project_l_research_model()

    export_result = export_corpus(

        {
            "query": query,
            "answer": answer["answer"]
        },

        "exports/test_research_brain.json"

    )

    export_result = export_corpus(

        {
            "query": query,
            "answer": answer["answer"]
        },

        "exports/test_research_brain.json"

    )

    return {

        "agent":
            "Research Brain",

        "query":
            query,

        "route":
            route["route"],

        "memory_hit":
            memory["memory_hit"],

        "memory_matches":
            memory["match_count"],

        "research_matches":
            research["match_count"],

        "answer_status":
            answer["status"],

        "answer":
            answer["answer"],

        "verified":
            verification["verified"],

        "report":
            report["summary"],

        "dashboard_status":
            dashboard["status"],

        "knowledge_matches":
            knowledge["match_count"],

        "pattern_matches":
            patterns["match_count"],

        "wisdom_matches":
            wisdom["match_count"],

        "intuition_matches":
            intuition["match_count"],

        "brain_v2_status":
            brain_v2["status"],

        "research_model_status":
            research_model["status"],

        "export_status":
            export_result["status"],

        "status":
            "processed"

    }

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    memory_sample = [

        {
            "content":
                "Exercise improves cognition"
        }

    ]

    research_sample = [

        {
            "question":
                "How does exercise affect cognition?",

            "summary":
                "Exercise improves cognition"
        }

    ]

    result = run_research_brain(

        "exercise",

        memory_sample,

        research_sample

    )

    print(result)

    assert result["memory_hit"] is True

    assert result["research_matches"] == 1

    assert result["answer_status"] == "answer_found"

    assert result["answer"] == \
        "Exercise improves cognition"
























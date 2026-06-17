# =====================================================
# KNOWLEDGE GRAPH
# TIER 2 - AODS 12
# =====================================================

from typing import List, Dict, Any


def build_knowledge_graph(
    relationships: List[Dict[str, Any]]
) -> Dict:

    nodes = set()

    edges = []

    for item in relationships or []:

        source = item.get(
            "entity1",
            ""
        )

        target = item.get(
            "entity2",
            ""
        )

        relation = item.get(
            "relationship",
            ""
        )

        if source:
            nodes.add(source)

        if target:
            nodes.add(target)

        if source and target:

            edges.append({

                "source":
                    source,

                "target":
                    target,

                "relationship":
                    relation

            })

    return {

        "agent":
            "Knowledge Graph",

        "node_count":
            len(nodes),

        "edge_count":
            len(edges),

        "nodes":
            sorted(list(nodes)),

        "edges":
            edges

    }


if __name__ == "__main__":

    sample = [

        {

            "entity1":
                "Exercise",

            "entity2":
                "Dementia Risk",

            "relationship":
                "reduces"

        },

        {

            "entity1":
                "Sleep",

            "entity2":
                "Cognition",

            "relationship":
                "improves"

        }

    ]

    result = build_knowledge_graph(
        sample
    )

    print(result)

    assert result["node_count"] == 4

    assert result["edge_count"] == 2


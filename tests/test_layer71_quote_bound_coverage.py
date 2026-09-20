import json
from hashlib import sha256

from core.cognition.evidence_evaluation import normalise
from core.cognition.publication_repair import (
    coverage_contract,
    evaluate_publication_coverage,
)


def qhash(text):
    return sha256(normalise(text).encode("utf-8")).hexdigest()


def excerpt_hash(text):
    return sha256(text.encode("utf-8")).hexdigest()


SUPPORTING = "Recovery timeline included detox, meetings and sponsor work."
UNRELATED = "The same record also mentioned a holiday booking."
DIRECTION = "Current direction is focused on building a meaningful life."

EVIDENCE_ROWS = [
    {
        "source": "raw_catchall:1",
        "quote_source": SUPPORTING,
        "role": "user",
    },
    {
        "source": "raw_catchall:1",
        "quote_source": UNRELATED,
        "role": "user",
    },
    {
        "source": "memory_project_l:9",
        "quote_source": DIRECTION,
        "role": "user",
    },
]

MANIFEST = {
    "represented_parts": ["recovery timeline", "current direction"],
    "part_sources": {
        "recovery timeline": ["raw_catchall:1"],
        "current direction": ["memory_project_l:9"],
    },
    "part_evidence": {
        "recovery timeline": [
            {
                "source": "raw_catchall:1",
                "excerpt_sha256": excerpt_hash(SUPPORTING),
            }
        ],
        "current direction": [
            {
                "source": "memory_project_l:9",
                "excerpt_sha256": excerpt_hash(DIRECTION),
            }
        ],
    },
}


def audit(*checks):
    return {
        "status": "citation_checks_passed",
        "blocks_checked": len(checks),
        "blocks_withheld": 0,
        "citations_checked": sum(len(c["citations"]) for c in checks),
        "checks": list(checks),
    }


def passed(block, source, quote):
    return {
        "block": block,
        "kind": "fact",
        "passed": True,
        "issues": [],
        "citations": [
            {
                "source": source,
                "quote_sha256": qhash(quote),
            }
        ],
    }


def raw_answer(text, covers, source, quote):
    return json.dumps({
        "blocks": [
            {
                "kind": "fact",
                "text": text,
                "covers": covers,
                "citations": [{"source": source, "quote": quote}],
            }
        ]
    })


def test_layer71_accepts_quote_from_part_bound_frozen_excerpt():
    quote = "Recovery timeline included detox"
    raw = raw_answer(
        "Recovery included detox.",
        ["recovery timeline"],
        "raw_catchall:1",
        quote,
    )
    coverage = evaluate_publication_coverage(
        raw,
        audit(passed(1, "raw_catchall:1", quote)),
        MANIFEST,
        evidence_rows=EVIDENCE_ROWS,
    )

    assert coverage["quote_bound"] is True
    assert coverage["version"] == "3.0"
    assert coverage["covered_parts"] == ["recovery timeline"]
    assert coverage["quote_mismatch_count"] == 0


def test_layer71_rejects_unrelated_quote_from_correct_source_id():
    quote = "The same record also mentioned a holiday booking."
    raw = raw_answer(
        "Recovery timeline was addressed.",
        ["recovery timeline"],
        "raw_catchall:1",
        quote,
    )
    coverage = evaluate_publication_coverage(
        raw,
        audit(passed(1, "raw_catchall:1", quote)),
        MANIFEST,
        evidence_rows=EVIDENCE_ROWS,
    )

    assert coverage["covered_parts"] == []
    assert coverage["missing_parts"] == ["recovery timeline", "current direction"]
    assert coverage["source_mismatch_count"] == 0
    assert coverage["quote_mismatch_count"] == 1
    assert coverage["quote_mismatches"][0]["part"] == "recovery timeline"


def test_layer71_fails_closed_when_quote_binding_declared_but_rows_unavailable():
    quote = "Recovery timeline included detox"
    raw = raw_answer(
        "Recovery included detox.",
        ["recovery timeline"],
        "raw_catchall:1",
        quote,
    )
    coverage = evaluate_publication_coverage(
        raw,
        audit(passed(1, "raw_catchall:1", quote)),
        MANIFEST,
        evidence_rows=None,
    )

    assert coverage["quote_bound"] is True
    assert coverage["covered_parts"] == []
    assert coverage["quote_mismatch_count"] == 1


def test_layer71_duplicate_source_only_accepts_the_bound_excerpt_variant():
    good_quote = "Recovery timeline included detox"
    bad_quote = "holiday booking"

    good = evaluate_publication_coverage(
        raw_answer(
            "Recovery included detox.",
            ["recovery timeline"],
            "raw_catchall:1",
            good_quote,
        ),
        audit(passed(1, "raw_catchall:1", good_quote)),
        MANIFEST,
        evidence_rows=EVIDENCE_ROWS,
    )
    bad = evaluate_publication_coverage(
        raw_answer(
            "Recovery was covered.",
            ["recovery timeline"],
            "raw_catchall:1",
            bad_quote,
        ),
        audit(passed(1, "raw_catchall:1", bad_quote)),
        MANIFEST,
        evidence_rows=EVIDENCE_ROWS,
    )

    assert good["covered_parts"] == ["recovery timeline"]
    assert bad["covered_parts"] == []
    assert bad["quote_mismatch_count"] == 1


def test_layer71_contract_states_quote_binding_rule_without_exposing_hashes():
    contract = coverage_contract(MANIFEST)

    assert "LAYER 71 QUOTE BINDING" in contract
    assert "exact continuous quote" in contract
    assert "excerpt_sha256" not in contract
    assert excerpt_hash(SUPPORTING) not in contract


def test_layer71_source_mismatch_still_fails_before_quote_check():
    quote = DIRECTION
    raw = raw_answer(
        "Recovery timeline was addressed.",
        ["recovery timeline"],
        "memory_project_l:9",
        quote,
    )
    coverage = evaluate_publication_coverage(
        raw,
        audit(passed(1, "memory_project_l:9", quote)),
        MANIFEST,
        evidence_rows=EVIDENCE_ROWS,
    )

    assert coverage["source_mismatch_count"] == 1
    assert coverage["quote_mismatch_count"] == 0
    assert coverage["covered_parts"] == []


def test_layer71_live_server_passes_frozen_evidence_rows_to_both_coverage_checks():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "api" / "server.py").read_text(encoding="utf-8")

    assert source.count("evidence_rows=evidence_rows") >= 2
    assert "exact quote from a frozen evidence excerpt" in source

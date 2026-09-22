"""Bounded, continuous source windows for ordinary evidence-backed recall.

Selection changes what is visible, never the source text or its provenance.
Separate windows remain separate evidence entries; they cannot form a synthetic quote.
"""
import re
from bisect import bisect_right


def recall_windows(content: str, query: str, expanded_terms=(), *, limit=2400):
    if not content:
        return []
    if len(content) <= limit:
        return [(0, content)]
    stop = set("what where which how many about remember recall know tell please my me you your the and that this with from have had do did earned wanted next confirmed details anything unsure separate".split())

    def words(value):
        return {word.rstrip("s") for word in re.findall(r"[a-z]{3,}", value.lower()) if word not in stop}

    direct = words(query)
    expanded = set().union(*(words(str(term)) for term in expanded_terms)) if expanded_terms else set()
    terms = direct | expanded
    # Candidate boundaries preserve sentence/paragraph endings where possible.
    boundaries = [0] + [m.end() for m in re.finditer(r"(?<=[.!?])\s+|\n+", content)] + [len(content)]
    width = max(1, limit // 2)
    candidates = []
    for start in boundaries[:-1]:
        if start >= len(content):
            continue
        end_index = bisect_right(boundaries, start + width) - 1
        end = boundaries[end_index] if boundaries[end_index] > start else min(len(content), start + width)
        text = content[start:end].strip()
        offset = start + len(content[start:end]) - len(content[start:end].lstrip())
        hits = words(text) & terms
        candidates.append((offset, text, hits))
    chosen, covered = [], set()
    for _ in range(2):
        available = [item for item in candidates if not any(
            item[0] < pos + len(text) and pos < item[0] + len(item[1]) for pos, text in chosen)]
        if not available:
            break
        def score(item):
            novel = item[2] - covered
            return (4 * len(novel & direct) + len(novel - direct), len(item[2]), -item[0])
        best = max(available, key=score)
        if chosen and not best[2] - covered:
            break
        chosen.append((best[0], best[1]))
        covered.update(best[2])
    return sorted(chosen)

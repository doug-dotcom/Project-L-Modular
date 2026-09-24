# Layer 137 — flexible saved-answer search

Saved review defaults to All words, any order: every whitespace-separated search term must occur somewhere in the checked question, displayed answer or status. Matching remains case-insensitive and literal, with no regular expressions or stemming. Exact phrase retains contiguous-text matching for more precise searches.

The Match selector works with existing status filters and ordering, stays selected through refresh, and changes results without extra requests. Clear filters empties the search and status filter while retaining the selected matching mode. Only checked tasks are searchable; rejected answer content remains excluded.

Validation covers mixed case and whitespace, terms across question/answer/status, missing terms, literal punctuation, exact phrases, switching modes, refresh and clearing filters. Phone visual testing remains outstanding.

"""Process-wide cache generations shared by memory readers and writers."""

from threading import Lock


_LOCK = Lock()
_GENERATIONS = {
    "raw": 0,
    "long_term": 0,
}


def cache_generation(cache_name):
    """Return the current generation for a known recall cache."""
    if cache_name not in _GENERATIONS:
        raise ValueError(f"Unknown recall cache: {cache_name}")
    with _LOCK:
        return _GENERATIONS[cache_name]


def invalidate_recall_caches(raw=False, long_term=False):
    """Advance selected generations after a successful memory write.

    Calling without a selection invalidates both caches, which is useful for
    maintenance operations whose affected layer is not known precisely.
    """
    if not raw and not long_term:
        raw = True
        long_term = True

    with _LOCK:
        if raw:
            _GENERATIONS["raw"] += 1
        if long_term:
            _GENERATIONS["long_term"] += 1
        return dict(_GENERATIONS)

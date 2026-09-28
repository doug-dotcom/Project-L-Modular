"""Deployment smoke for Project L's pinned Shine-AI trace trust surface."""

from services import shine_runtime_service as runtime


def main() -> None:
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
    })
    keyset, error = runtime._shine_ai_verification_keyset()
    if error is not None or not isinstance(keyset, dict):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            + str(error or "keyset-unavailable")
        )
    print(
        "Project L Shine-AI trace trust smoke: PASS "
        f"keys={len(keyset.get('verification_keys') or {})}"
    )


if __name__ == "__main__":
    main()

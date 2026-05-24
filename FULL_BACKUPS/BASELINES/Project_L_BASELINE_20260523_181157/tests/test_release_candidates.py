from services.runtime_release_candidate_service import (
    create_release_candidate,
    candidate_status,
    recent_candidates,
    latest_candidate,
    candidate_summary
)

print("")
print("===================================")
print("AODS 84 VALIDATION")
print("===================================")
print("")

print("CREATE RELEASE CANDIDATE:")
print(
    create_release_candidate(
        label="AODS84_RC1"
    )
)

print("")
print("CANDIDATE STATUS:")
print(candidate_status())

print("")
print("LATEST CANDIDATE:")
print(latest_candidate())

print("")
print("RECENT CANDIDATES:")
print(recent_candidates())

print("")
print("CANDIDATE SUMMARY:")
print(candidate_summary())

from services.runtime_replay_service import (
    replay_status,
    build_replay_snapshot,
    recent_replays,
    replay_timeline,
    replay_summary
)

print("")
print("===================================")
print("AODS 69 VALIDATION")
print("===================================")
print("")

print("INITIAL STATUS:")
print(replay_status())

print("")
print("BUILD SNAPSHOT:")
print(
    build_replay_snapshot(
        label="aods69_validation",
        limit=10
    )
)

print("")
print("TIMELINE:")
print(replay_timeline(limit=10))

print("")
print("SUMMARY:")
print(replay_summary(limit=10))

print("")
print("RECENT REPLAYS:")
print(recent_replays())

from services.runtime_snapshot_service import (
    create_snapshot,
    snapshot_status,
    recent_snapshots,
    latest_snapshot,
    snapshot_summary
)

print("")
print("===================================")
print("AODS 85 VALIDATION")
print("===================================")
print("")

print("CREATE SNAPSHOT:")
print(
    create_snapshot(
        label="AODS85_CANONICAL"
    )
)

print("")
print("SNAPSHOT STATUS:")
print(snapshot_status())

print("")
print("LATEST SNAPSHOT:")
print(latest_snapshot())

print("")
print("RECENT SNAPSHOTS:")
print(recent_snapshots())

print("")
print("SNAPSHOT SUMMARY:")
print(snapshot_summary())

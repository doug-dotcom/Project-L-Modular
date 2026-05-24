from services.runtime_restoration_service import (
    restore_latest_snapshot,
    restore_by_label,
    restoration_status,
    recent_restorations,
    restoration_summary
)

print("")
print("===================================")
print("AODS 86 VALIDATION")
print("===================================")
print("")

print("RESTORE LATEST:")
print(restore_latest_snapshot())

print("")
print("RESTORE BY LABEL:")
print(
    restore_by_label(
        "AODS85_CANONICAL"
    )
)

print("")
print("RESTORATION STATUS:")
print(restoration_status())

print("")
print("RECENT RESTORATIONS:")
print(recent_restorations())

print("")
print("RESTORATION SUMMARY:")
print(restoration_summary())

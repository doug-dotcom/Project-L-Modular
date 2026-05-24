from services.runtime_finalisation_service import (
    finalisation_check,
    create_finalisation_record,
    finalisation_status,
    finalisation_brief
)

print("")
print("===================================")
print("AODS 89 VALIDATION")
print("===================================")
print("")

print("FINALISATION CHECK:")
print(finalisation_check())

print("")
print("CREATE FINALISATION RECORD:")
print(
    create_finalisation_record(
        label="AODS89_FINAL_RUNTIME"
    )
)

print("")
print("FINALISATION STATUS:")
print(finalisation_status())

print("")
print("FINALISATION BRIEF:")
print(finalisation_brief())

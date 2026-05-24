from services.runtime_audit_service import (
    record_event,
    ledger_status,
    recent_events,
    validate_chain
)

print("")
print("===================================")
print("AODS 67 VALIDATION RECOVERY")
print("===================================")
print("")

print("INITIAL STATUS:")
print(ledger_status())

print("")

record_event(
    event_type="validation",
    source="aods67_recovery",
    payload={
        "message": "audit recovery validation"
    },
    severity="normal"
)

print("LEDGER STATUS:")
print(ledger_status())

print("")
print("RECENT EVENTS:")
print(recent_events())

print("")
print("CHAIN VALIDATION:")
print(validate_chain())

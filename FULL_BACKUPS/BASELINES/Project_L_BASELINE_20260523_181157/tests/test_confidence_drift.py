from services.runtime_confidence_service import (
    confidence_score,
    drift_score,
    runtime_alignment,
    drift_signals
)

print("")
print("===================================")
print("AODS 70 VALIDATION")
print("===================================")
print("")

print("CONFIDENCE SCORE:")
print(confidence_score())

print("")
print("DRIFT SCORE:")
print(drift_score())

print("")
print("ALIGNMENT:")
print(runtime_alignment())

print("")
print("DRIFT SIGNALS:")
print(drift_signals())

from services.runtime_strategy_service import (
    strategic_priority,
    build_plan,
    recent_plans,
    planning_status,
    strategic_snapshot
)

print("")
print("===================================")
print("AODS 71 VALIDATION")
print("===================================")
print("")

print("STRATEGIC PRIORITY:")
print(strategic_priority())

print("")
print("BUILD PLAN:")
print(
    build_plan(
        title="Runtime Stability Expansion",
        objective="Expand runtime safely while controlling drift",
        steps=[
            "Monitor alignment",
            "Reduce runtime noise",
            "Expand capabilities gradually"
        ],
        priority="high"
    )
)

print("")
print("PLANNING STATUS:")
print(planning_status())

print("")
print("STRATEGIC SNAPSHOT:")
print(strategic_snapshot())

print("")
print("RECENT PLANS:")
print(recent_plans())

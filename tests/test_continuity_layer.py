from core.cognition.controller import plan_cognition


def test_go_requires_memory_for_continuity():
    plan = plan_cognition("Go")
    assert plan["needs"]["continuity"] is True
    assert plan["needs"]["memory"] is True
    assert plan["signals"]["continuity"] is True
    assert plan["problem_type"] == "personal_recall"


def test_next_go_requires_memory_for_continuity():
    plan = plan_cognition("Next go 👊")
    assert plan["needs"]["continuity"] is True
    assert plan["needs"]["memory"] is True


def test_explicit_resume_requires_memory():
    plan = plan_cognition("Pick up where we left off")
    assert plan["needs"]["continuity"] is True
    assert plan["needs"]["memory"] is True


def test_new_topic_does_not_force_continuity():
    plan = plan_cognition("Tell me a joke about penguins")
    assert plan["needs"]["continuity"] is False

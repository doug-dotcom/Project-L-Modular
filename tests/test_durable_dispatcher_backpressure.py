from pathlib import Path

from core.cognition.durable_tasks import TaskRunner


def test_task_runner_reusable_default_stays_two_slots():
    class Store:
        pass

    runner = TaskRunner(Store(), lambda request: request)
    assert runner.slots == 2


def test_production_server_uses_one_durable_dispatcher_slot():
    source = Path("api/server.py").read_text(encoding="utf-8")

    assert (
        "task_runner = TaskRunner("
        "task_store, execute_durable_request, slots=1)"
        in source
    )


def test_single_slot_change_does_not_alter_claim_backoff_or_reaper_defaults():
    source = Path("core/cognition/durable_tasks.py").read_text(encoding="utf-8")

    assert "slots=2" in source
    assert "reaper_interval_seconds=30" in source
    assert "reaper_failure_backoff_seconds=60" in source
    assert "delay = min(60, 3 * (2 ** min(failures - 1, 5)))" in source

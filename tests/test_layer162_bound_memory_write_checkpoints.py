"""Layer 162 — durable memory writes require fresh bound checkpoints."""
from pathlib import Path
import re


SERVER = Path("api/server.py")


def source():
    return SERVER.read_text(encoding="utf-8")


def test_user_memory_writes_are_guarded_before_each_persistence_step():
    text = source()

    short_checkpoint = text.index('checkpoint("saving_short_term_user")')
    short_write = text.index("short_term_user = write_live_short_term(")
    raw_checkpoint = text.index('checkpoint("saving_raw_user")')
    raw_write = text.index('raw_user_row = write_raw_catchall(')

    assert short_checkpoint < short_write < raw_checkpoint < raw_write


def test_every_user_memory_pipeline_entry_has_a_fresh_bound_checkpoint():
    text = source()

    marker = 'checkpoint("processing_user_memory")'
    pipeline = "run_brain_pipeline(raw_user_row)"

    assert text.count(marker) == 2
    assert text.count(pipeline) == 2

    first_marker = text.index(marker)
    first_pipeline = text.index(pipeline)
    second_marker = text.index(marker, first_marker + 1)
    second_pipeline = text.index(pipeline, first_pipeline + 1)

    assert first_marker < first_pipeline < second_marker < second_pipeline


def test_assistant_memory_writes_are_guarded_independently():
    text = source()

    complete_turn = text.index(
        'cognitive_packet["working_memory"] = active_context_service.complete_turn('
    )
    short_checkpoint = text.index('checkpoint("saving_short_term_answer")')
    short_write = text.index("short_term_assistant = write_live_short_term(")
    raw_checkpoint = text.index('checkpoint("saving_raw_answer")')
    raw_write = text.index('raw_assistant_row = write_raw_catchall(')
    receipt = text.index("assistant_persistence = sealed_reply_persistence_receipt(")

    assert (
        complete_turn
        < short_checkpoint
        < short_write
        < raw_checkpoint
        < raw_write
        < receipt
    )


def test_layer162_replaces_shared_write_guard_with_specific_boundaries():
    text = source()

    assert 'checkpoint("saving_user_message")' not in text
    assert 'checkpoint("saving_answer")' not in text

    release_layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', text)
    ]
    assert len(release_layers) == 3
    assert len(set(release_layers)) == 1
    assert release_layers[0] >= 162

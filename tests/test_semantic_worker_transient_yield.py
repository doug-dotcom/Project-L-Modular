from pathlib import Path


WORKER = Path("supabase/functions/l-semantic-worker/index.ts")


def source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_semantic_worker_treats_transient_database_codes_as_yield_signals():
    ts = source()

    assert 'const TRANSIENT_DATABASE_CODES=new Set(["57014","PGRST002","PGRST003"]);' in ts
    assert 'function transientDatabaseCode(error:unknown)' in ts
    assert 'leaseRecovery:"expiry"' in ts
    assert 'reason:"transient_database_busy"' in ts
    assert 'retryAfterSeconds:1' in ts


def test_semantic_completion_timeout_defers_without_failure_write_amplification():
    ts = source()

    eval_complete = ts.index('deferredBody("eval_complete",code')
    eval_failure = ts.index('db.rpc("project_l_fail_eval_embedding_v1"')
    unit_complete = ts.index('deferredBody("unit_complete",code')
    unit_failure = ts.index('db.rpc("project_l_fail_semantic_unit_v1"')

    assert eval_complete < eval_failure
    assert unit_complete < unit_failure
    assert 'return json(deferredBody("eval_complete",code' in ts
    assert 'return json(deferredBody("unit_complete",code' in ts
    assert ts.count('db.rpc("project_l_fail_eval_embedding_v1"') == 1
    assert ts.count('db.rpc("project_l_fail_semantic_unit_v1"') == 1


def test_semantic_failure_persistence_timeout_also_yields():
    ts = source()

    assert 'const failed=await db.rpc("project_l_fail_eval_embedding_v1"' in ts
    assert 'return json(deferredBody("eval_failure_persist",code' in ts
    assert 'const failed=await db.rpc("project_l_fail_semantic_unit_v1"' in ts
    assert 'return json(deferredBody("unit_failure_persist",code' in ts


def test_semantic_worker_preserves_existing_work_bounds():
    ts = source()

    assert 'const rawEvalLimit=Number(body.evalLimit??8);' in ts
    assert 'const rawBatchLimit=Number(body.batchLimit??16);' in ts
    assert '? Math.min(Math.max(rawEvalLimit,0),16)' in ts
    assert '? Math.min(Math.max(rawBatchLimit,0),32)' in ts
    assert 'const CLAIM_RETRY_DELAY_MS=350;' in ts

import threading
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from core.cognition.durable_tasks import TaskStore, TaskRunner, CONTEXT, checkpoint, owner_identity, request_hash


class FakeStore:
    def __init__(self):
        self.finished = []
        self.progressed = []
        self.owned = True
    def progress(self, request_id, worker, stage=None):
        self.progressed.append(stage)
        return self.owned
    def finish(self, request_id, worker, payload, status='ready'):
        self.finished.append((status, payload))
        return self.owned


def test_runner_checkpoints_and_saves_actual_result():
    store = FakeStore()
    def execute(request):
        checkpoint('reasoning')
        return {'reply': request['message']}
    TaskRunner(store, execute).run_one({'request_id': str(uuid4()), 'request': {'message': 'actual answer'}}, str(uuid4()))
    assert store.finished == [('ready', {'reply': 'actual answer'})]
    assert store.progressed == ['reasoning']
    assert CONTEXT.task is None


def test_lost_lease_stops_before_next_action():
    store = FakeStore()
    store.owned = False
    effects = []
    def execute(request):
        checkpoint('connected_actions')
        effects.append('action')
    TaskRunner(store, execute).run_one({'request_id': str(uuid4()), 'request': {}}, str(uuid4()))
    assert not effects
    assert store.finished[0][0] == 'failed'


def test_failed_result_write_retries_save_without_repeating_work():
    class Store(FakeStore):
        attempts = 0
        def finish(self, *args, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError()
            return super().finish(*args, **kwargs)
    store = Store()
    effects = []
    TaskRunner(store, lambda request: effects.append('once') or {'reply': 'done'}).run_one(
        {'request_id': str(uuid4()), 'request': {}}, str(uuid4()))
    assert effects == ['once']
    assert store.attempts == 2


def test_execution_exception_is_terminal_not_retried():
    store = FakeStore()
    def execute(request):
        raise RuntimeError('private error detail')
    TaskRunner(store, execute).run_one({'request_id': str(uuid4()), 'request': {}}, str(uuid4()))
    assert len(store.finished) == 1
    assert store.finished[0][0] == 'failed'
    assert 'private' not in str(store.finished)


def test_provider_failure_receipt_remains_failed_and_recoverable():
    store = FakeStore()
    payload = {'reply': 'Please try again.', 'error': True, 'model_receipt': {'status': 'incomplete'}}
    TaskRunner(store, lambda _: payload).run_one({'request_id': str(uuid4()), 'request': {}}, str(uuid4()))
    assert store.finished == [('failed', payload)]


def test_owner_secret_is_hashed_and_not_in_request_payload():
    seen = {}
    class Client:
        def rpc(self, name, params):
            seen.update(params)
            return SimpleNamespace(execute=lambda: SimpleNamespace(data={'status': 'queued'}))
    token = 'secret-recovery-token-' * 3
    req = {'request_id': str(uuid4()), 'message': 'test', 'conversation_id': None}
    TaskStore(Client()).submit(req, token)
    assert token not in str(seen)
    assert seen['p_user'] == owner_identity(token)[0]
    assert seen['p_hash'] == request_hash(req)
    assert request_hash(req) != request_hash({**req, 'message': 'changed'})


def test_result_lookup_filters_by_both_owner_and_request():
    filters = {}
    class Query:
        def select(self, columns): return self
        def eq(self, key, value): filters[key] = value; return self
        def limit(self, value): return self
        def execute(self): return SimpleNamespace(data=[])
    store = TaskStore(SimpleNamespace(table=lambda name: Query()))
    request_id = str(uuid4())
    assert store.get(request_id, 'x' * 64) == {'status': 'not_found'}
    assert filters == {'request_id': request_id, 'user_id': owner_identity('x' * 64)[0], 'owner_hash': owner_identity('x' * 64)[1]}


def test_durable_answers_never_enter_unprotected_legacy_cache():
    from api import server
    request_id = str(uuid4())
    CONTEXT.task = ('test', request_id, 'worker')
    try:
        server.store_chat_result(request_id, 'ready', {'reply': 'private'})
    finally:
        CONTEXT.task = None
    assert server.recover_chat_result(request_id) == {'status': 'not_found'}


def test_start_does_not_acknowledge_when_database_is_down(monkeypatch):
    from api import server
    def submit(*args): raise ConnectionError()
    monkeypatch.setattr(server, 'task_store', SimpleNamespace(submit=submit))
    with pytest.raises(HTTPException) as exc:
        server.start_chat(server.ChatRequest(message='test', request_id=str(uuid4())), 'x' * 64)
    assert exc.value.status_code == 503


@pytest.mark.parametrize('status,code', [('conflict', 409), ('not_found', 404)])
def test_start_rejects_id_reuse(monkeypatch, status, code):
    from api import server
    monkeypatch.setattr(server, 'task_store', SimpleNamespace(submit=lambda *args: {'status': status}))
    with pytest.raises(HTTPException) as exc:
        server.start_chat(server.ChatRequest(message='test', request_id=str(uuid4())), 'x' * 64)
    assert exc.value.status_code == code


def test_get_database_outage_does_not_fall_back_to_cached_answer(monkeypatch):
    from api import server
    def get(*args): raise ConnectionError()
    monkeypatch.setattr(server, 'task_store', SimpleNamespace(get=get))
    with pytest.raises(HTTPException) as exc:
        server.recover_chat_result(str(uuid4()), 'x' * 64)
    assert exc.value.status_code == 503

class PollEvent:
    def __init__(self, stop_after):
        self.waits = []
        self.stop_after = stop_after
    def is_set(self):
        return len(self.waits) >= self.stop_after
    def wait(self, seconds):
        self.waits.append(seconds)
        return self.is_set()


def test_dispatcher_backs_off_caps_and_resets_after_recovery(monkeypatch, caplog):
    from core.cognition import durable_tasks
    monkeypatch.setattr(durable_tasks.random, 'uniform', lambda a, b: 0)
    class Store:
        calls = 0
        def claim(self, worker):
            self.calls += 1
            if self.calls <= 7 or self.calls == 9:
                raise ConnectionError('secret-token must never enter logs')
            return None
    store = Store()
    runner = TaskRunner(store, lambda request: None)
    runner.stop_event = PollEvent(9)
    with caplog.at_level('INFO'):
        runner.loop()
    assert runner.stop_event.waits == [3, 6, 12, 24, 48, 60, 60, 3, 3]
    assert store.calls == 9
    assert 'error_type=ConnectionError' in caplog.text
    assert 'recovered after 7 failed polls' in caplog.text
    assert 'secret-token' not in caplog.text


def test_uncertain_claim_is_not_replayed(monkeypatch):
    from core.cognition import durable_tasks
    monkeypatch.setattr(durable_tasks.random, 'uniform', lambda a, b: 0)
    effects = []
    class Store(FakeStore):
        calls = 0
        def claim(self, worker):
            self.calls += 1
            if self.calls == 1:
                # The database committed this claim but its response was lost.
                raise TimeoutError('response lost')
            if self.calls == 2:
                return {'request_id': str(uuid4()), 'request': {'message': 'next task'}}
            return None
    store = Store()
    runner = TaskRunner(store, lambda request: effects.append(request['message']) or {'reply': 'done'})
    runner.stop_event = PollEvent(2)
    runner.loop()
    assert effects == ['next task']
    assert len(store.finished) == 1
    assert runner.stop_event.waits == [3, 3]

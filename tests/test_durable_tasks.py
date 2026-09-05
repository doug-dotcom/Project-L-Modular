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

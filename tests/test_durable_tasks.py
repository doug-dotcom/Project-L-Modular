import threading
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from core.cognition.durable_tasks import TaskStore, TaskRunner, CONTEXT, checkpoint, owner_identity, request_hash


def bound_task(message='actual answer'):
    request_id = str(uuid4())
    request = {'request_id': request_id, 'message': message}
    return {
        'request_id': request_id,
        'request': request,
        'input_hash': request_hash(request),
        '_request_integrity': {
            'version': '1.0',
            'status': 'verified',
            'valid': True,
            'issues': [],
            'request_id_bound': True,
        },
    }


class FakeStore:
    def __init__(self):
        self.finished = []
        self.progressed = []
        self.rejected = []
        self.owned = True
    def progress_bound(self, request_id, worker, input_hash, request, stage=None):
        self.progressed.append(stage)
        return self.owned
    def finish_bound(self, request_id, worker, input_hash, request, payload, status='ready'):
        self.finished.append((status, payload))
        return self.owned
    def reject_bound(self, request_id, worker, input_hash, request, payload):
        self.rejected.append(payload)
        return self.owned


def test_runner_checkpoints_and_saves_actual_result():
    store = FakeStore()
    def execute(request):
        checkpoint('reasoning')
        return {'reply': request['message']}
    TaskRunner(store, execute).run_one(bound_task(), str(uuid4()))
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
    TaskRunner(store, execute).run_one(bound_task('connected action'), str(uuid4()))
    assert not effects
    assert store.finished[0][0] == 'failed'


def test_failed_result_write_retries_save_without_repeating_work():
    class Store(FakeStore):
        attempts = 0
        def finish_bound(self, *args, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectionError()
            return super().finish_bound(*args, **kwargs)
    store = Store()
    effects = []
    TaskRunner(store, lambda request: effects.append('once') or {'reply': 'done'}).run_one(
        bound_task('once'), str(uuid4()))
    assert effects == ['once']
    assert store.attempts == 2


def test_execution_exception_is_terminal_not_retried():
    store = FakeStore()
    def execute(request):
        raise RuntimeError('private error detail')
    TaskRunner(store, execute).run_one(bound_task('failure'), str(uuid4()))
    assert len(store.finished) == 1
    assert store.finished[0][0] == 'failed'
    assert 'private' not in str(store.finished)


def test_provider_failure_receipt_remains_failed_and_recoverable():
    store = FakeStore()
    payload = {'reply': 'Please try again.', 'error': True, 'model_receipt': {'status': 'incomplete'}}
    TaskRunner(store, lambda _: payload).run_one(bound_task('provider failure'), str(uuid4()))
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
                return bound_task('next task')
            return None
    store = Store()
    runner = TaskRunner(store, lambda request: effects.append(request['message']) or {'reply': 'done'})
    runner.stop_event = PollEvent(2)
    runner.loop()
    assert effects == ['next task']
    assert len(store.finished) == 1
    assert runner.stop_event.waits == [3, 3]


def test_dedicated_task_transport_authenticates_and_does_not_retry_uncertain_claim(monkeypatch):
    import httpx
    from core.cognition import durable_tasks
    requests = []
    client_options = {}
    real_client = httpx.Client

    def respond(request):
        requests.append(request)
        assert request.headers['apikey'] == 'synthetic-service-key'
        assert request.headers['authorization'] == 'Bearer synthetic-service-key'
        if len(requests) == 1:
            raise httpx.RemoteProtocolError('private upstream detail')
        return httpx.Response(200, json=[])

    def client(**kwargs):
        client_options.update(kwargs)
        return real_client(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(durable_tasks.httpx, 'Client', client)
    db = durable_tasks.task_database_client('https://example.supabase.co', 'synthetic-service-key')
    try:
        store = TaskStore(db)
        with pytest.raises(httpx.RemoteProtocolError):
            store.claim(str(uuid4()))
        assert len(requests) == 1, 'An uncertain claim must not be retried'
        assert store.claim(str(uuid4())) is None
        assert requests[0].url.path == '/rest/v1/rpc/l_task_claim'
        assert client_options['http2'] is False
        assert client_options['timeout'].read < 120
        assert client_options['timeout'].pool < 120
        assert db.options.persist_session is False
    finally:
        db.options.httpx_client.close()


def test_task_transport_is_not_created_without_credentials():
    from core.cognition.durable_tasks import task_database_client
    assert task_database_client('', '') is None


def test_start_enables_recovery_logs_without_enabling_http_debug(monkeypatch):
    import logging
    from core.cognition import durable_tasks
    old_level = durable_tasks.LOG.level
    try:
        runner = TaskRunner(FakeStore(), lambda request: {}, slots=0)
        runner.start()
        assert durable_tasks.LOG.isEnabledFor(logging.INFO)
        assert not durable_tasks.LOG.isEnabledFor(logging.DEBUG)
    finally:
        durable_tasks.LOG.setLevel(old_level)

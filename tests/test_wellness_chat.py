from fastapi import FastAPI
from fastapi.testclient import TestClient
from api import wellness_chat as bridge

OWNER = '41ba75a2-0fbd-470a-bb60-f5c4d691436a'
TOKEN = 'w' * 48
REQUEST = 'cedc775c-0dbf-4e30-87be-045ccba5d730'
CONVERSATION = '510136ae-9da6-482b-bdae-b620c041071c'

class Store:
    def __init__(self): self.rows = {}; self.writes = 0
    def submit(self, envelope, token):
        key = envelope['request_id']
        if key in self.rows:
            return {'status': 'pending' if self.rows[key][0] == envelope else 'conflict'}
        self.rows[key] = (envelope, token); self.writes += 1
        return {'status': 'pending'}
    def get(self, request_id, token):
        if request_id not in self.rows or self.rows[request_id][1] != token: return {'status': 'not_found'}
        return {'status': 'ready', 'result': {'reply': 'Tell me more about that.'}}

def setup(monkeypatch):
    monkeypatch.setenv('WELLNESS_CHAT_SERVICE_TOKEN', TOKEN)
    monkeypatch.setenv('WELLNESS_CHAT_OWNER_ID', OWNER)
    store = Store(); bridge.register_wellness_chat_store(store)
    app = FastAPI(); app.include_router(bridge.router)
    return TestClient(app), store

def body(**extra):
    return dict(user_id=OWNER, request_id=REQUEST, conversation_id=CONVERSATION, message='A difficult day', **extra)

def test_owner_service_boundary(monkeypatch):
    client, store = setup(monkeypatch)
    assert client.post('/internal/wellness/chat/start', json=body()).status_code == 401
    b = body(); b['user_id'] = CONVERSATION
    assert client.post('/internal/wellness/chat/start', headers={'X-Wellness-Chat-Token': TOKEN}, json=b).status_code == 403
    assert store.writes == 0

def test_durable_retry_scope_and_reply(monkeypatch):
    client, store = setup(monkeypatch); headers = {'X-Wellness-Chat-Token': TOKEN}
    for _ in range(2): assert client.post('/internal/wellness/chat/start', json=body(), headers=headers).json()['durable']
    assert store.writes == 1
    envelope, _ = store.rows[REQUEST]
    assert envelope['conversation_id'] == 'wellness_' + CONVERSATION
    assert 'shine_runtime' not in envelope
    b = body(); b['message'] = 'Changed'
    assert client.post('/internal/wellness/chat/start', json=b, headers=headers).status_code == 409
    result = client.get(f'/internal/wellness/chat/result/{REQUEST}?user_id={OWNER}', headers=headers).json()
    assert result == {'status': 'ready', 'reply': 'Tell me more about that.'}

def test_failed_answer_is_not_presented_as_reply(monkeypatch):
    client, store = setup(monkeypatch)
    store.get = lambda *args: {'status': 'ready', 'result': {'reply': 'Error text', 'error': True}}
    assert client.get(f'/internal/wellness/chat/result/{REQUEST}?user_id={OWNER}', headers={'X-Wellness-Chat-Token': TOKEN}).json() == {'status': 'failed'}

def test_unconfigured_and_invalid_message(monkeypatch):
    client, _ = setup(monkeypatch); headers = {'X-Wellness-Chat-Token': TOKEN}
    b = body(); b['message'] = ' '
    assert client.post('/internal/wellness/chat/start', json=b, headers=headers).status_code == 422
    b['message'] = 'x' * 6001
    assert client.post('/internal/wellness/chat/start', json=b, headers=headers).status_code == 422
    monkeypatch.delenv('WELLNESS_CHAT_SERVICE_TOKEN')
    assert client.post('/internal/wellness/chat/start', json=body(), headers=headers).status_code == 503

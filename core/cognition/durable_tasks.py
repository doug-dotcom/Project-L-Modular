"""Persistent chat queue; completed results survive process and browser restarts.

A random browser secret is a recovery capability, NOT a verified human identity.
Only its hash is persisted. In-flight work is never automatically replayed.
"""
import hashlib
import json
import logging
import threading
from uuid import UUID, uuid4

LOG = logging.getLogger(__name__)
CONTEXT = threading.local()


def owner_identity(token):
    if not isinstance(token, str) or not 32 <= len(token) <= 256:
        raise ValueError('A recovery token of 32–256 characters is required')
    digest = hashlib.sha256(token.encode()).hexdigest()
    return str(UUID(digest[:32])), digest


def request_hash(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class TaskStore:
    def __init__(self, client):
        self.client = client

    def rpc(self, name, params):
        if self.client is None:
            raise RuntimeError('Task database unavailable')
        return self.client.rpc(name, params).execute().data

    def submit(self, request, token):
        user_id, owner = owner_identity(token)
        return self.rpc('l_task_submit', {'p_id': request['request_id'], 'p_user': user_id,
            'p_owner': owner, 'p_hash': request_hash(request), 'p_request': request})

    def get(self, request_id, token):
        user_id, owner = owner_identity(token)
        rows = (self.client.table('l_chat_tasks')
                .select('status,result,checkpoint,lease_until,created_at,updated_at')
                .eq('request_id', request_id).eq('user_id', user_id).eq('owner_hash', owner)
                .limit(1).execute().data)
        if not rows:
            return {'status': 'not_found'}
        row = rows[0]
        temporal = (row.get('result') or {}).get('cognition', {}).get('temporal_memory')
        if temporal:
            from core.cognition.temporal_memory import snapshot_freshness
            # Preserve the original payload/receipt. Freshness is a separate read-time annotation.
            row['freshness'] = snapshot_freshness(self.client, temporal)
        # A stopped process is visible even before the dispatcher next sweeps leases.
        if row['status'] == 'running' and row.get('lease_until'):
            from datetime import datetime, timezone
            if datetime.fromisoformat(row['lease_until'].replace('Z', '+00:00')) < datetime.now(timezone.utc):
                row['status'] = 'interrupted'
        return {**row, 'durable': True, 'request_id': request_id}

    def claim(self, worker):
        rows = self.rpc('l_task_claim', {'p_worker': worker})
        return rows[0] if rows else None

    def progress(self, request_id, worker, checkpoint=None):
        return self.rpc('l_task_progress', {'p_id': request_id, 'p_worker': worker, 'p_checkpoint': checkpoint})

    def finish(self, request_id, worker, payload, status='ready'):
        return self.rpc('l_task_finish', {'p_id': request_id, 'p_worker': worker,
                                        'p_status': status, 'p_result': payload})


def checkpoint(stage):
    task = getattr(CONTEXT, 'task', None)
    if task:
        store, request_id, worker = task
        if not store.progress(request_id, worker, stage):
            raise RuntimeError('Task lease lost; work stopped')


class TaskRunner:
    def __init__(self, store, execute, slots=2):
        self.store, self.execute, self.slots = store, execute, slots
        self.stop_event = threading.Event()
        self.threads = []

    def start(self):
        if self.threads:
            return
        for index in range(self.slots):
            thread = threading.Thread(target=self.loop, daemon=True, name=f'l-durable-{index}')
            self.threads.append(thread)
            thread.start()

    def stop(self):
        self.stop_event.set()

    def loop(self):
        worker = str(uuid4())
        while not self.stop_event.is_set():
            try:
                task = self.store.claim(worker)
                if task:
                    self.run_one(task, worker)
                    continue
            except Exception:
                LOG.warning('Durable task dispatcher unavailable', exc_info=False)
            self.stop_event.wait(3)

    def run_one(self, task, worker):
        request_id = task['request_id']
        done = threading.Event()
        def heartbeat():
            while not done.wait(15):
                try:
                    if not self.store.progress(request_id, worker):
                        return
                except Exception:
                    LOG.warning('Task heartbeat unavailable')
        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        CONTEXT.task = (self.store, request_id, worker)
        try:
            payload = self.execute(task['request'])
            # Retry only the idempotent result write, never the cognition/actions.
            for attempt in range(3):
                try:
                    if not self.store.finish(request_id, worker, payload,
                                             status='failed' if payload.get('error') else 'ready'):
                        LOG.warning('Task result rejected: lease lost')
                    break
                except Exception:
                    if attempt == 2:
                        LOG.warning('Task result could not be persisted')
                    else:
                        done.wait(1)
        except Exception:
            try:
                self.store.finish(request_id, worker, {
                    'reply': 'This task stopped before completion. Please review any actions before starting it again.',
                    'error': True}, status='failed')
            except Exception:
                LOG.warning('Task failure could not be persisted')
        finally:
            CONTEXT.task = None
            done.set()
            pulse.join(timeout=1)

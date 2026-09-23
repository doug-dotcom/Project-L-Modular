"""Persistent chat queue; completed results survive process and browser restarts.

A random browser secret is a recovery capability, NOT a verified human identity.
Only its hash is persisted. In-flight work is never automatically replayed.
"""
import hashlib
import json
import logging
import random
import threading
import traceback
from uuid import UUID, uuid4

import httpx
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from core.cognition.delivery_integrity import (
    require_chat_delivery_payload,
    verify_chat_delivery_payload,
)
from core.cognition.recovery_provenance import (
    require_recovered_answer_payload,
    verify_recovered_answer_payload,
)

LOG = logging.getLogger(__name__)
CONTEXT = threading.local()


def task_database_client(url, key):
    """Isolate leases and queue polling from the shared recall HTTP/2 pool.

    A protocol error cannot tell us whether a claim committed. Do not add
    transport retries; the dispatcher keeps its backoff and no-replay rules.
    Bound I/O well below the two-minute lease so heartbeat failures return.
    """
    if not url or not key:
        return None
    transport = httpx.Client(
        http2=False,
        timeout=httpx.Timeout(20, connect=5, pool=5),
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4,
                            keepalive_expiry=5),
    )
    try:
        return create_client(url, key, options=SyncClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
    except Exception:
        transport.close()
        raise


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
        result_payload = row.get('result')
        if result_payload is not None or row['status'] == 'ready':
            delivery = verify_chat_delivery_payload(
                result_payload,
                expected_request_id=request_id,
            )
            row['delivery_integrity'] = delivery
            if not delivery.get('valid'):
                row['status'] = 'failed'
                row['result'] = {
                    'reply': (
                        'The saved answer failed delivery integrity verification. '
                        'Please submit the request again.'
                    ),
                    'error': True,
                }
                return {**row, 'durable': True, 'request_id': request_id}

            recovery = verify_recovered_answer_payload(
                result_payload,
                expected_request_id=request_id,
            )
            row['recovery_integrity'] = recovery
            if not recovery.get('valid'):
                row['status'] = 'failed'
                row['result'] = {
                    'reply': (
                        'The saved answer failed provenance verification. '
                        'Please submit the request again.'
                    ),
                    'error': True,
                }
                return {**row, 'durable': True, 'request_id': request_id}
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
        require_chat_delivery_payload(
            payload,
            expected_request_id=request_id,
        )
        require_recovered_answer_payload(
            payload,
            expected_request_id=request_id,
        )
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
        # Uvicorn configures its own loggers, not the root application logger.
        # Make recovery visible without enabling HTTP request/body debug logs.
        logging.basicConfig(level=logging.WARNING)
        LOG.setLevel(logging.INFO)
        LOG.info('Durable task dispatcher starting: slots=%d', self.slots)
        for index in range(self.slots):
            thread = threading.Thread(target=self.loop, daemon=True, name=f'l-durable-{index}')
            self.threads.append(thread)
            thread.start()

    def stop(self):
        self.stop_event.set()

    def loop(self):
        worker = str(uuid4())
        failures = 0
        while not self.stop_event.is_set():
            try:
                task = self.store.claim(worker)
                if failures:
                    LOG.info('Durable task dispatcher recovered after %d failed polls', failures)
                failures = 0
                if task:
                    self.run_one(task, worker)
                    continue
            except Exception as exc:
                failures += 1
                # Do not log exception text: it may contain request data or credentials.
                # No immediate RPC retry: a timed-out claim may already own a task.
                delay = min(60, 3 * (2 ** min(failures - 1, 5)))
                delay = min(60, delay + random.uniform(0, delay * 0.2))
                frames = traceback.extract_tb(exc.__traceback__)
                last = frames[-1] if frames else None
                LOG.warning(
                    'Durable task dispatcher unavailable: error_type=%s failures=%d retry_in=%.1fs source=%s:%s function=%s',
                    type(exc).__name__, failures, delay,
                    last.filename.rsplit('/', 1)[-1].rsplit('\\', 1)[-1] if last else 'unknown',
                    last.lineno if last else 'unknown', last.name if last else 'unknown',
                )
                self.stop_event.wait(delay)
                continue
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
        except Exception as exc:
            # Safe production diagnostic: type + final source location only. Never log
            # exception text, request content, retrieved evidence, tokens or credentials.
            frames = traceback.extract_tb(exc.__traceback__)
            last = frames[-1] if frames else None
            LOG.error(
                'Durable task failed: error_type=%s source=%s:%s function=%s',
                type(exc).__name__,
                last.filename.rsplit('/', 1)[-1].rsplit('\\', 1)[-1] if last else 'unknown',
                last.lineno if last else 'unknown',
                last.name if last else 'unknown',
            )
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

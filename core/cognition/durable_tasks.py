"""Persistent chat queue; completed results survive process and browser restarts.

A random browser secret is a recovery capability, NOT a verified human identity.
Only its hash is persisted. In-flight work is never automatically replayed.
"""
import hashlib
import json
import logging
import random
import re
import threading
import traceback
from uuid import UUID, uuid4

import httpx
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from core.cognition.action_receipt import (
    require_payload_action_receipt,
    verify_payload_action_receipt,
)
from core.cognition.delivery_integrity import (
    require_chat_delivery_payload,
    verify_chat_delivery_payload,
)
from core.cognition.document_evidence import (
    require_document_evidence_binding,
    verify_document_evidence_binding,
)
from core.cognition.recovery_provenance import (
    require_recovered_answer_payload,
    verify_recovered_answer_payload,
)

LOG = logging.getLogger(__name__)
CONTEXT = threading.local()


class DurableTaskBindingError(RuntimeError):
    """A durable task no longer owns the exact request/lease it claimed."""


def current_task_request_id():
    """Return the durable request bound to this execution thread, if any."""
    task = getattr(CONTEXT, 'task', None)
    if not task or len(task) != 5:
        return ''
    return str(task[1] or '')



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


def verify_task_request_integrity(request_id, request, input_hash):
    """Verify the stored durable request before trusting any saved task result."""
    issues = []
    if not isinstance(request, dict):
        issues.append('request_payload_missing_or_malformed')
    else:
        embedded = request.get('request_id')
        if not isinstance(embedded, str) or embedded != str(request_id):
            issues.append('request_id_binding_mismatch')
        try:
            expected_hash = request_hash(request)
        except Exception:
            expected_hash = ''
            issues.append('request_payload_not_hashable')
        if not re.fullmatch(r'[0-9a-f]{64}', str(input_hash or '')):
            issues.append('input_hash_shape_invalid')
        elif expected_hash and str(input_hash) != expected_hash:
            issues.append('request_hash_mismatch')

    if not isinstance(request, dict) and not re.fullmatch(r'[0-9a-f]{64}', str(input_hash or '')):
        issues.append('input_hash_shape_invalid')

    return {
        'version': '1.0',
        'status': 'verified' if not issues else 'mismatch',
        'valid': not issues,
        'issues': issues,
        'request_id_bound': not issues,
    }


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
                .select('status,result,request,input_hash,checkpoint,lease_until,created_at,updated_at')
                .eq('request_id', request_id).eq('user_id', user_id).eq('owner_hash', owner)
                .limit(1).execute().data)
        if not rows:
            return {'status': 'not_found'}
        row = rows[0]
        request_fields_present = 'request' in row or 'input_hash' in row
        task_request = row.pop('request', None)
        stored_input_hash = row.pop('input_hash', None)
        if request_fields_present:
            request_integrity = verify_task_request_integrity(request_id, task_request, stored_input_hash)
        else:
            # Compatibility for synthetic/pre-contract readers that did not select
            # the request columns. The production query always selects both fields.
            request_integrity = {
                'version': '1.0', 'status': 'legacy_unchecked', 'valid': True,
                'issues': [], 'request_id_bound': False,
            }
        row['request_integrity'] = request_integrity
        if not request_integrity.get('valid'):
            row['status'] = 'failed'
            row['result'] = {
                'reply': (
                    'The saved task failed request integrity verification. '
                    'Please submit the request again.'
                ),
                'error': True,
            }
            return {**row, 'durable': True, 'request_id': request_id}
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

            action_receipt = verify_payload_action_receipt(
                result_payload,
                expected_request_id=request_id,
            )
            row['action_receipt_integrity'] = action_receipt
            if not action_receipt.get('valid'):
                row['status'] = 'failed'
                row['result'] = {
                    'reply': (
                        'The saved answer failed connected-action receipt verification. '
                        'Please check the external service before retrying.'
                    ),
                    'error': True,
                }
                return {**row, 'durable': True, 'request_id': request_id}

            if row['status'] == 'ready' and isinstance(task_request, dict) and task_request.get('kind') == 'document_evidence':
                source_binding = verify_document_evidence_binding(task_request, result_payload)
                row['document_evidence_binding'] = source_binding
                if not source_binding.get('valid'):
                    row['status'] = 'failed'
                    row['result'] = {
                        'reply': (
                            'The saved file answer failed source binding verification. '
                            'Please submit the question again from the original file.'
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
        if not rows:
            return None
        task = rows[0]
        task['_request_integrity'] = verify_task_request_integrity(
            task.get('request_id'), task.get('request'), task.get('input_hash')
        )
        return task

    def progress_bound(self, request_id, worker, input_hash, request, checkpoint=None):
        return self.rpc('l_task_progress_bound', {
            'p_id': request_id,
            'p_worker': worker,
            'p_hash': input_hash,
            'p_request': request,
            'p_checkpoint': checkpoint,
        })

    def _verify_finish_payload(self, request_id, payload):
        require_chat_delivery_payload(
            payload,
            expected_request_id=request_id,
        )
        require_recovered_answer_payload(
            payload,
            expected_request_id=request_id,
        )
        require_payload_action_receipt(
            payload,
            expected_request_id=request_id,
        )

    def finish_bound(self, request_id, worker, input_hash, request, payload, status='ready'):
        self._verify_finish_payload(request_id, payload)
        return self.rpc('l_task_finish_bound', {
            'p_id': request_id,
            'p_worker': worker,
            'p_hash': input_hash,
            'p_request': request,
            'p_status': status,
            'p_result': payload,
        })

    def reject_bound(self, request_id, worker, input_hash, request, payload):
        self._verify_finish_payload(request_id, payload)
        return self.rpc('l_task_reject_bound', {
            'p_id': request_id,
            'p_worker': worker,
            'p_hash': input_hash,
            'p_request': request,
            'p_result': payload,
        })


def checkpoint(stage):
    task = getattr(CONTEXT, 'task', None)
    if not task:
        return
    if len(task) != 5:
        raise DurableTaskBindingError('Durable task binding missing; work stopped')
    store, request_id, worker, input_hash, request = task
    if not store.progress_bound(request_id, worker, input_hash, request, stage):
        raise DurableTaskBindingError('Task lease or request binding lost; work stopped')


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
        request_integrity = task.get('_request_integrity')
        try:
            claimed_request = json.loads(json.dumps(
                task.get('request'), sort_keys=True, separators=(',', ':')
            ))
        except Exception:
            claimed_request = None
        claimed_hash = task.get('input_hash')

        if not isinstance(request_integrity, dict) or request_integrity.get('valid') is not True:
            issues = (
                request_integrity.get('issues', [])
                if isinstance(request_integrity, dict)
                else ['claim_integrity_marker_missing']
            )
            LOG.warning(
                'Durable task request integrity failed before execution: request_id=%s issues=%s',
                request_id,
                ','.join(str(issue) for issue in issues),
            )
            if claimed_request is not None and isinstance(claimed_hash, str):
                try:
                    self.store.reject_bound(
                        request_id,
                        worker,
                        claimed_hash,
                        claimed_request,
                        {
                            'reply': (
                                'This task stopped before execution because its saved request '
                                'failed integrity verification. Please submit it again.'
                            ),
                            'error': True,
                        },
                    )
                except Exception:
                    LOG.warning('Invalid durable task could not be marked failed')
            return

        if (
            not isinstance(claimed_request, dict)
            or not isinstance(claimed_hash, str)
            or re.fullmatch(r'[0-9a-f]{64}', claimed_hash) is None
        ):
            LOG.warning(
                'Verified durable task lost its claim binding before execution: request_id=%s',
                request_id,
            )
            return

        done = threading.Event()
        def heartbeat():
            while not done.wait(15):
                try:
                    if not self.store.progress_bound(
                        request_id, worker, claimed_hash, claimed_request
                    ):
                        return
                except Exception:
                    LOG.warning('Task heartbeat unavailable')
        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        CONTEXT.task = (
            self.store, request_id, worker, claimed_hash, claimed_request
        )
        try:
            payload = self.execute(task['request'])
            if task['request'].get('kind') == 'document_evidence' and not payload.get('error'):
                require_document_evidence_binding(task['request'], payload)
            # Retry only the idempotent result write, never the cognition/actions.
            for attempt in range(3):
                try:
                    saved = self.store.finish_bound(
                        request_id,
                        worker,
                        claimed_hash,
                        claimed_request,
                        payload,
                        status='failed' if payload.get('error') else 'ready',
                    )
                    if not saved:
                        LOG.warning('Task result rejected: lease or request binding lost')
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
                failure = {
                    'reply': 'This task stopped before completion. Please review any actions before starting it again.',
                    'error': True,
                }
                self.store.finish_bound(
                    request_id,
                    worker,
                    claimed_hash,
                    claimed_request,
                    failure,
                    status='failed',
                )
            except Exception:
                LOG.warning('Task failure could not be persisted')
        finally:
            CONTEXT.task = None
            done.set()
            pulse.join(timeout=1)

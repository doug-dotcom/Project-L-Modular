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
    verify_action_receipt,
    verify_journaled_action_receipt,
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


def _task_binding_parts(task):
    """Return the durable binding plus optional cooperative-loss signal."""
    if not task:
        return None
    if len(task) == 5:
        store, request_id, worker, input_hash, request = task
        return store, request_id, worker, input_hash, request, None
    if len(task) == 6:
        store, request_id, worker, input_hash, request, binding_lost = task
        if not hasattr(binding_lost, 'is_set') or not hasattr(binding_lost, 'set'):
            raise DurableTaskBindingError('Durable task binding signal invalid; work stopped')
        return store, request_id, worker, input_hash, request, binding_lost
    raise DurableTaskBindingError('Durable task binding missing; work stopped')


def current_task_request_id():
    """Return the durable request bound to this execution thread, if any."""
    task = getattr(CONTEXT, 'task', None)
    if not task:
        return ''
    parts = _task_binding_parts(task)
    return str(parts[1] or '')


def record_current_action_receipt(receipt):
    """Persist one provider-confirmed action immediately when running durably."""
    task = getattr(CONTEXT, 'task', None)
    if not task:
        return False

    store, request_id, worker, input_hash, request, binding_lost = _task_binding_parts(task)
    if binding_lost is not None and binding_lost.is_set():
        raise DurableTaskBindingError('Task lease or request binding lost; work stopped')

    try:
        frozen_receipt = json.loads(json.dumps(
            receipt, sort_keys=True, separators=(',', ':')
        ))
    except Exception:
        raise DurableTaskBindingError('Connected action receipt invalid; work stopped')

    verification = verify_action_receipt(
        frozen_receipt,
        expected_request_id=request_id,
    )
    if not verification.get('valid'):
        raise DurableTaskBindingError('Connected action receipt invalid; work stopped')

    try:
        saved = store.record_action_bound(
            request_id,
            worker,
            input_hash,
            request,
            frozen_receipt,
        )
    except Exception:
        # A provider action may already have happened and the journal write may
        # have committed even if its acknowledgement was lost. Never replay the
        # external action or retry the journal mutation. Reconcile with one
        # read-only, exact-bound check instead.
        try:
            saved = store.confirm_action_bound(
                request_id,
                worker,
                input_hash,
                request,
                frozen_receipt,
            )
        except Exception:
            saved = False
        if not saved:
            raise DurableTaskBindingError(
                'Connected action journal unavailable; work stopped'
            )
    if not saved:
        if binding_lost is not None:
            binding_lost.set()
        raise DurableTaskBindingError(
            'Connected action journal rejected; work stopped'
        )

    # Preserve the exact successfully journaled receipt for any later terminal
    # failure in this same worker thread. This is process-local evidence only;
    # the durable journal remains authoritative.
    CONTEXT.action_receipt = frozen_receipt
    return True



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
                .select('status,result,action_receipt,request,input_hash,checkpoint,lease_until,created_at,updated_at')
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
        journal_receipt = row.get('action_receipt')
        journal_integrity = verify_journaled_action_receipt(
            journal_receipt,
            row.get('result'),
            expected_request_id=request_id,
        )
        row['action_journal_integrity'] = journal_integrity
        if not journal_integrity.get('valid'):
            row['status'] = 'failed'
            row['result'] = {
                'reply': (
                    'The saved task failed connected-action journal verification. '
                    'Please check the external service before retrying.'
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
        if (
            row['status'] == 'interrupted'
            and row.get('result') is None
            and journal_integrity.get('valid')
            and journal_integrity.get('present')
        ):
            row['result'] = {
                'reply': (
                    'A connected action was confirmed before this task stopped, '
                    'but the final answer was not saved. Check the external service '
                    'before submitting the action again.'
                ),
                'error': True,
            }
        return {**row, 'durable': True, 'request_id': request_id}

    def claim(self, worker, claim_token=None):
        token = str(claim_token or uuid4())
        rows = self.rpc('l_task_claim_bound', {
            'p_worker': worker,
            'p_claim_token': token,
        })
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

    def record_action_bound(self, request_id, worker, input_hash, request, receipt):
        return self.rpc('l_task_record_action_bound', {
            'p_id': request_id,
            'p_worker': worker,
            'p_hash': input_hash,
            'p_request': request,
            'p_receipt': receipt,
        })

    def confirm_action_bound(self, request_id, worker, input_hash, request, receipt):
        return self.rpc('l_task_confirm_action_bound', {
            'p_id': request_id,
            'p_worker': worker,
            'p_hash': input_hash,
            'p_request': request,
            'p_receipt': receipt,
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

    def confirm_finish_bound(
        self, request_id, worker, input_hash, request, payload, status='ready'
    ):
        self._verify_finish_payload(request_id, payload)
        return self.rpc('l_task_confirm_finish_bound', {
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
    store, request_id, worker, input_hash, request, binding_lost = _task_binding_parts(task)
    if binding_lost is not None and binding_lost.is_set():
        raise DurableTaskBindingError('Task lease or request binding lost; work stopped')
    if not store.progress_bound(request_id, worker, input_hash, request, stage):
        if binding_lost is not None:
            binding_lost.set()
        raise DurableTaskBindingError('Task lease or request binding lost; work stopped')
    if binding_lost is not None and binding_lost.is_set():
        raise DurableTaskBindingError('Task lease or request binding lost; work stopped')


class TaskRunner:
    def __init__(self, store, execute, slots=2, heartbeat_seconds=15):
        self.store, self.execute, self.slots = store, execute, slots
        self.heartbeat_seconds = max(0.001, float(heartbeat_seconds))
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
        claim_token = None
        failures = 0
        while not self.stop_event.is_set():
            try:
                if claim_token is None:
                    claim_token = str(uuid4())
                task = self.store.claim(worker, claim_token=claim_token)
                # A returned response, including an empty queue response, resolves
                # this one-shot claim attempt. Transport failures keep the same
                # token so a retry can only recover that exact claim.
                claim_token = None
                if failures:
                    LOG.info('Durable task dispatcher recovered after %d failed polls', failures)
                failures = 0
                if task:
                    self.run_one(task, worker)
                    continue
            except Exception as exc:
                failures += 1
                # Do not log exception text: it may contain request data or credentials.
                # The claim token is intentionally retained across transport
                # uncertainty so the next poll cannot claim a different task.
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

    def _persist_terminal_bound(
        self,
        request_id,
        worker,
        input_hash,
        request,
        payload,
        status,
        done,
    ):
        """Persist one terminal result and prove ambiguous acknowledgements."""
        ambiguous_write_seen = False
        for attempt in range(3):
            try:
                saved = self.store.finish_bound(
                    request_id,
                    worker,
                    input_hash,
                    request,
                    payload,
                    status=status,
                )
            except Exception:
                ambiguous_write_seen = True
                # The exact terminal write may have committed even if its
                # acknowledgement was lost. Reconcile read-only before any
                # idempotent retry; never rerun cognition or connected actions.
                try:
                    if self.store.confirm_finish_bound(
                        request_id,
                        worker,
                        input_hash,
                        request,
                        payload,
                        status=status,
                    ):
                        return True
                except Exception:
                    pass
                if attempt == 2:
                    return False
                done.wait(1)
                continue

            if saved:
                return True

            # A clean false response is definitive when no earlier write was
            # transport-ambiguous. Preserve the Layer 160 bound-rejection
            # contract: do not retry a mutation the database rejected.
            if not ambiguous_write_seen:
                return False

            # After an earlier ambiguous write, an exact retry can return false
            # because that earlier attempt actually committed. Prove the stored
            # terminal payload before treating this as rejection.
            try:
                if self.store.confirm_finish_bound(
                    request_id,
                    worker,
                    input_hash,
                    request,
                    payload,
                    status=status,
                ):
                    return True
            except Exception:
                if attempt < 2:
                    done.wait(1)
                    continue
                return False
            return False

        return False

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
        binding_lost = threading.Event()
        def heartbeat():
            while not done.wait(self.heartbeat_seconds):
                try:
                    if not self.store.progress_bound(
                        request_id, worker, claimed_hash, claimed_request
                    ):
                        binding_lost.set()
                        LOG.warning('Task heartbeat rejected: lease or request binding lost')
                        return
                except Exception:
                    # Transport uncertainty does not prove ownership was lost. The
                    # next checkpoint still performs a bound database verification.
                    LOG.warning('Task heartbeat unavailable')
        pulse = threading.Thread(target=heartbeat, daemon=True)
        pulse.start()
        CONTEXT.task = (
            self.store, request_id, worker, claimed_hash, claimed_request,
            binding_lost,
        )
        CONTEXT.action_receipt = None
        try:
            payload = self.execute(task['request'])
            if binding_lost.is_set():
                raise DurableTaskBindingError(
                    'Task lease or request binding lost; work stopped'
                )
            if task['request'].get('kind') == 'document_evidence' and not payload.get('error'):
                require_document_evidence_binding(task['request'], payload)
            terminal_status = 'failed' if payload.get('error') else 'ready'
            saved = self._persist_terminal_bound(
                request_id,
                worker,
                claimed_hash,
                claimed_request,
                payload,
                terminal_status,
                done,
            )
            if not saved:
                LOG.warning('Task result could not be confirmed as persisted')
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
                journaled_receipt = getattr(CONTEXT, 'action_receipt', None)
                if isinstance(journaled_receipt, dict):
                    failure['route'] = {
                        'handled': True,
                        'capability': journaled_receipt.get('capability', 'connected_action'),
                        'status': 'error',
                        'action_receipt': journaled_receipt,
                        'action_receipt_verification': verify_action_receipt(
                            journaled_receipt,
                            expected_request_id=request_id,
                        ),
                    }
                saved_failure = self._persist_terminal_bound(
                    request_id,
                    worker,
                    claimed_hash,
                    claimed_request,
                    failure,
                    'failed',
                    done,
                )
                if not saved_failure:
                    LOG.warning(
                        'Task failure could not be confirmed as persisted: '
                        'lease, request binding or action journal mismatch'
                    )
            except Exception:
                LOG.warning('Task failure could not be persisted')
        finally:
            CONTEXT.task = None
            CONTEXT.action_receipt = None
            done.set()
            pulse.join(timeout=1)

/* Lease, verify and surface delayed Concierge completions as ordinary L messages. */
(() => {
    const POLL_MS = 30000;
    const REQUEST_TIMEOUT_MS = 15000;
    const SEEN_KEY = 'project-l-concierge-completions-v1';
    const MAX_SEEN = 100;
    const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    const SHA256 = /^[a-f0-9]{64}$/;

    let timer = null;
    let inFlight = null;

    function accountReady() {
        return document.documentElement.dataset.account === 'ready';
    }

    function activeConversationId() {
        try {
            const value = typeof window.currentConversationId === 'function'
                ? window.currentConversationId()
                : '';
            return UUID.test(value) ? value : '';
        } catch (_) {
            return '';
        }
    }

    function seenIds() {
        try {
            const value = JSON.parse(localStorage.getItem(SEEN_KEY) || '[]');
            return Array.isArray(value)
                ? value.filter(item => typeof item === 'string' && UUID.test(item)).slice(-MAX_SEEN)
                : [];
        } catch (_) {
            return [];
        }
    }

    function rememberSeen(eventId) {
        try {
            const next = seenIds().filter(item => item !== eventId);
            next.push(eventId);
            localStorage.setItem(SEEN_KEY, JSON.stringify(next.slice(-MAX_SEEN)));
        } catch (_) {
            // The server lease remains unacknowledged if local bookkeeping fails.
            throw new Error('completion-local-bookkeeping-failed');
        }
    }

    async function requestJson(path, options = {}) {
        const controller = new AbortController();
        const timerId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        try {
            const response = await fetch(path, {
                ...options,
                cache: 'no-store',
                signal: controller.signal,
            });
            const data = await response.json();
            if (!response.ok || !data || typeof data !== 'object' || Array.isArray(data)) {
                throw new Error('completion-request-failed');
            }
            return data;
        } finally {
            clearTimeout(timerId);
        }
    }

    async function acknowledge(eventId, leaseToken) {
        const data = await requestJson(
            '/foundation/completions/' + encodeURIComponent(eventId) + '/ack',
            {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({lease_token: leaseToken}),
            },
        );
        if (data.acknowledged !== true) {
            throw new Error('completion-acknowledgement-failed');
        }
    }

    async function verifyCompletionReceipt(receipt, expected) {
        if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) {
            throw new Error('completion-receipt-invalid');
        }
        const fields = [
            'version',
            'status',
            'request_id',
            'source_conversation_id',
            'source_message_id',
            'answer_generated_at',
            'final_answer_sha256',
            'result_packet_sha256',
            'receipt_sha256',
        ];
        if (
            Object.keys(receipt).length !== fields.length
            || !fields.every(field => Object.hasOwn(receipt, field) && typeof receipt[field] === 'string')
            || receipt.version !== '1.0'
            || receipt.status !== 'sealed'
            || !UUID.test(receipt.request_id)
            || !SHA256.test(receipt.final_answer_sha256)
            || !SHA256.test(receipt.result_packet_sha256)
            || !SHA256.test(receipt.receipt_sha256)
            || !Number.isFinite(Date.parse(receipt.answer_generated_at))
        ) {
            throw new Error('completion-receipt-invalid');
        }

        for (const [field, value] of Object.entries(expected || {})) {
            if (value != null && String(receipt[field] || '') !== String(value)) {
                throw new Error('completion-receipt-binding-mismatch');
            }
        }

        if (typeof window.sha256HexText !== 'function') {
            throw new Error('completion-hash-verifier-unavailable');
        }
        const body = Object.fromEntries(
            fields
                .filter(field => field !== 'receipt_sha256')
                .sort()
                .map(field => [field, receipt[field]])
        );
        const actual = await window.sha256HexText(JSON.stringify(body));
        if (actual !== receipt.receipt_sha256) {
            throw new Error('completion-receipt-integrity-mismatch');
        }
        return receipt;
    }

    function pointInTimeText(answer, freshness, generatedAt) {
        const parsed = new Date(generatedAt);
        const when = Number.isFinite(parsed.getTime())
            ? parsed.toLocaleString('en-AU', {dateStyle: 'medium', timeStyle: 'short'})
            : generatedAt;
        const status = String(freshness?.status || 'unavailable');
        let note;
        if (status === 'superseded') {
            note = `Delayed final answer — generated ${when}. Relevant tracked facts have since changed, so this is the original point-in-time answer, not a current answer.`;
        } else if (status === 'unchanged') {
            note = `Delayed final answer — generated ${when}. Its tracked temporal facts were rechecked and are unchanged.`;
        } else if (status === 'not_tracked') {
            note = `Delayed final answer — generated ${when}. This is a point-in-time answer; no temporal-fact freshness check applied.`;
        } else {
            note = `Delayed final answer — generated ${when}. I could not verify whether its tracked facts have changed.`;
        }
        return note + '\n\n' + answer;
    }

    async function verifiedAnswer(event, expectedConversationId) {
        const answer = typeof event.finalAnswer === 'string' ? event.finalAnswer.trim() : '';
        const declared = String(event.finalAnswerSha256 || '');
        const packetSha = String(event.resultPacketSha256 || '');
        const generatedAt = String(event.finalAnswerGeneratedAt || '');
        const requestId = String(event.requestId || '');
        const sourceConversationId = String(event.sourceConversationId || '');
        const sourceMessageId = String(event.sourceMessageId || '');
        if (
            !answer
            || answer.length > 50000
            || !SHA256.test(declared)
            || !SHA256.test(packetSha)
            || !UUID.test(requestId)
            || !Number.isFinite(Date.parse(generatedAt))
            || sourceConversationId !== expectedConversationId
        ) {
            throw new Error('completion-answer-invalid');
        }
        if (typeof window.sha256HexText !== 'function') {
            throw new Error('completion-hash-verifier-unavailable');
        }
        const actual = await window.sha256HexText(answer);
        if (actual !== declared) {
            throw new Error('completion-answer-integrity-mismatch');
        }
        const receipt = await verifyCompletionReceipt(event.completionReceipt, {
            request_id: requestId,
            source_conversation_id: sourceConversationId,
            source_message_id: sourceMessageId,
            answer_generated_at: generatedAt,
            final_answer_sha256: declared,
            result_packet_sha256: packetSha,
        });
        return {
            answer,
            receipt,
            freshness: event.freshness || {status: 'unavailable'},
            displayText: pointInTimeText(
                answer,
                event.freshness,
                receipt.answer_generated_at,
            ),
        };
    }

    function render(eventId, eventType, text) {
        const chat = document.getElementById('chat');
        if (!chat || typeof window.appendChatMessage !== 'function') {
            throw new Error('completion-chat-unavailable');
        }
        const alreadySeen = seenIds().includes(eventId);
        if (!alreadySeen) {
            window.appendChatMessage(chat, 'assistant', text);
            chat.scrollTop = chat.scrollHeight;
            rememberSeen(eventId);
        }
        window.dispatchEvent(new CustomEvent('l-concierge-completion-surfaced', {
            detail: {eventId, eventType},
        }));
    }

    async function delayedHistory(limit = 100) {
        const bounded = Number.isSafeInteger(limit)
            ? Math.max(1, Math.min(100, limit))
            : 100;
        const data = await requestJson(
            '/foundation/completions/history?limit=' + encodeURIComponent(String(bounded)),
            {method: 'GET'},
        );
        if (
            data.status !== 'ok'
            || data.version !== '2.0'
            || !Array.isArray(data.items)
            || data.items.length > bounded
        ) {
            throw new Error('completion-history-invalid');
        }

        const verified = [];
        for (const item of data.items) {
            if (!item || typeof item !== 'object' || Array.isArray(item)) {
                continue;
            }
            const requestId = String(item.request_id || '');
            const answer = typeof item.final_answer === 'string'
                ? item.final_answer.trim()
                : '';
            const answerSha = String(item.final_answer_sha256 || '');
            const packetSha = String(item.result_packet_sha256 || '');
            const requestText = typeof item.request_text === 'string'
                ? item.request_text
                : '';
            if (
                !UUID.test(requestId)
                || item.integrity !== 'verified'
                || !answer
                || answer.length > 50000
                || requestText.length > 100000
                || !SHA256.test(answerSha)
                || !SHA256.test(packetSha)
            ) {
                continue;
            }
            if (typeof window.sha256HexText !== 'function') {
                throw new Error('completion-hash-verifier-unavailable');
            }
            const actual = await window.sha256HexText(answer);
            if (actual !== answerSha) {
                continue;
            }
            const sourceConversationId = String(item.source_conversation_id || '');
            const sourceMessageId = String(item.source_message_id || '');
            const generatedAt = String(item.answer_generated_at || '');
            if (!Number.isFinite(Date.parse(generatedAt))) {
                continue;
            }
            let receipt;
            try {
                receipt = await verifyCompletionReceipt(item.completion_receipt, {
                    request_id: requestId,
                    source_conversation_id: sourceConversationId,
                    source_message_id: sourceMessageId,
                    answer_generated_at: generatedAt,
                    final_answer_sha256: answerSha,
                    result_packet_sha256: packetSha,
                });
            } catch (_) {
                continue;
            }
            const freshness = (
                item.freshness && typeof item.freshness === 'object' && !Array.isArray(item.freshness)
            ) ? item.freshness : {status: 'unavailable'};
            verified.push({
                requestId,
                sourceConversationId,
                sourceMessageId,
                requestText,
                finalAnswer: answer,
                displayAnswer: pointInTimeText(answer, freshness, generatedAt),
                finalAnswerSha256: answerSha,
                resultPacketSha256: packetSha,
                answerGeneratedAt: generatedAt,
                completionReceipt: receipt,
                freshness,
                completedAt: item.completed_at || null,
                updatedAt: item.updated_at || null,
            });
        }
        return verified;
    }

    async function pendingJobs(limit = 100) {
        const bounded = Number.isSafeInteger(limit)
            ? Math.max(1, Math.min(100, limit))
            : 100;
        const data = await requestJson(
            '/foundation/completions/pending?limit=' + encodeURIComponent(String(bounded)),
            {method: 'GET'},
        );
        if (
            data.status !== 'ok'
            || data.version !== '1.0'
            || !Array.isArray(data.items)
            || data.items.length > bounded
        ) {
            throw new Error('pending-concierge-jobs-invalid');
        }
        return data.items.flatMap(item => {
            if (!item || typeof item !== 'object' || Array.isArray(item)) return [];
            const requestId = String(item.request_id || '');
            const sourceConversationId = String(item.source_conversation_id || '');
            const requestText = typeof item.request_text === 'string' ? item.request_text : '';
            const capabilities = Array.isArray(item.capability_ids)
                ? item.capability_ids.map(value => String(value)).slice(0, 20)
                : [];
            if (
                !UUID.test(requestId)
                || !['ready', 'cancelling'].includes(String(item.status || ''))
                || requestText.length > 100000
                || capabilities.length < 1
            ) return [];
            return [{
                requestId,
                sourceConversationId,
                sourceMessageId: String(item.source_message_id || ''),
                requestText,
                status: String(item.status || ''),
                capabilityIds: capabilities,
                createdAt: item.created_at || null,
                updatedAt: item.updated_at || null,
            }];
        });
    }

    async function cancelPending(requestId) {
        const id = String(requestId || '');
        if (!UUID.test(id)) throw new Error('pending-concierge-request-invalid');
        const result = await requestJson(
            '/foundation/completions/' + encodeURIComponent(id) + '/cancel',
            {method: 'POST'},
        );
        if (!['cancelled', 'already-cancelled', 'cancelling', 'retired'].includes(String(result.status || ''))) {
            throw new Error('pending-concierge-cancellation-failed');
        }
        return result;
    }

    function cancellationReceiptText(job) {
        const integrity = String(job?.cancellation_receipt_integrity || '');
        const receipt = job?.cancellation_receipt;
        if (integrity === 'mismatch') {
            return 'Cancellation history exists, but its receipt failed integrity verification. I have not reconstructed what happened.';
        }
        if (!receipt || receipt.integrity !== 'verified') return '';

        const reason = String(receipt.reason_code || '');
        const cancelled = new Date(receipt.cancelled_at);
        const when = Number.isFinite(cancelled.getTime())
            ? cancelled.toLocaleString('en-AU', {dateStyle: 'medium', timeStyle: 'short'})
            : String(receipt.cancelled_at || 'unknown time');
        const progress = receipt.progress || {};
        const completed = Array.isArray(receipt.completed_capabilities)
            ? receipt.completed_capabilities : [];
        const pending = Array.isArray(receipt.pending_capabilities)
            ? receipt.pending_capabilities : [];
        const supersededBy = String(receipt.superseded_by_request_id || '');

        const lines = [];
        if (reason === 'superseded-by-newer-request') {
            lines.push(
                'Cancellation receipt — this delayed Concierge job was superseded by a newer request'
                + (UUID.test(supersededBy) ? ' (' + supersededBy + ')' : '')
                + '.'
            );
        } else if (reason === 'user-cancelled') {
            lines.push('Cancellation receipt — this delayed Concierge job was cancelled by you.');
        } else {
            lines.push('Cancellation receipt — delayed Concierge work stopped: ' + (reason || 'cancelled') + '.');
        }
        lines.push(
            'At cancellation, '
            + Number(progress.completed_before_cancellation || 0)
            + ' of '
            + Number(progress.total_steps || 0)
            + ' specialist steps had completed.'
        );
        if (completed.length) lines.push('Completed before cancellation: ' + completed.join(', ') + '.');
        if (pending.length) lines.push('Still pending at cancellation: ' + pending.join(', ') + '.');
        lines.push('Cancelled: ' + when + '.');
        if (SHA256.test(String(receipt.receipt_sha256 || ''))) {
            lines.push('Verified receipt SHA-256: ' + receipt.receipt_sha256 + '.');
        }
        return lines.join('\n');
    }

    function retirementReceiptText(job) {
        const integrity = String(job?.retirement_receipt_integrity || '');
        const receipt = job?.retirement_receipt;
        if (integrity === 'mismatch') {
            return 'Retirement history exists, but its receipt failed integrity verification. I have not reconstructed what happened.';
        }
        if (!receipt || receipt.integrity !== 'verified') return '';

        const retired = new Date(receipt.retired_at);
        const when = Number.isFinite(retired.getTime())
            ? retired.toLocaleString('en-AU', {dateStyle: 'medium', timeStyle: 'short'})
            : String(receipt.retired_at || 'unknown time');
        const age = Number(receipt.minimum_age_seconds || 0);
        const hours = age > 0 ? Math.round(age / 3600 * 10) / 10 : null;
        const capabilities = Array.isArray(receipt.requested_capabilities)
            ? receipt.requested_capabilities : [];

        const lines = [
            'Retirement receipt — this Concierge plan expired unused'
            + (hours ? ' after at least ' + hours + ' hour' + (hours === 1 ? '' : 's') : '')
            + '.',
            'Execution never started. No specialist checkpoint was written and no retry was queued.',
        ];
        if (capabilities.length) {
            lines.push('Planned capabilities: ' + capabilities.join(', ') + '.');
        }
        lines.push('Retired: ' + when + '.');
        if (SHA256.test(String(receipt.receipt_sha256 || ''))) {
            lines.push('Verified receipt SHA-256: ' + receipt.receipt_sha256 + '.');
        }
        return lines.join('\n');
    }

    function planTtlText(job) {
        const ttl = job?.plan_ttl;
        if (!ttl || ttl.server_authoritative !== true) return '';

        if (ttl.state === 'counting-down') {
            const seconds = Number(ttl.seconds_remaining);
            if (!Number.isSafeInteger(seconds) || seconds <= 0 || seconds > 3600) return '';
            const minutes = Math.ceil(seconds / 60);
            const expiry = new Date(ttl.expires_at);
            const when = Number.isFinite(expiry.getTime())
                ? expiry.toLocaleTimeString('en-AU', {hour: 'numeric', minute: '2-digit'})
                : null;
            const remaining = seconds < 90
                ? 'about a minute'
                : minutes + ' min';
            return 'Waiting to execute · expires in ' + remaining
                + (when ? ' (' + when + ')' : '') + '.';
        }
        if (ttl.state === 'expiry-due') {
            return 'Expiry due · Foundation will retire this unused plan before execution.';
        }
        if (ttl.state === 'started-exempt') {
            return 'Execution started · the one-hour plan deadline no longer applies.';
        }
        return '';
    }

    async function taskCentre(limit = 50) {
        const bounded = Number.isSafeInteger(limit)
            ? Math.max(1, Math.min(100, limit))
            : 50;
        const data = await requestJson(
            '/foundation/jobs?limit=' + encodeURIComponent(String(bounded)),
            {method: 'GET'},
        );
        if (
            data.status !== 'ok'
            || data.version !== '1.0'
            || !Array.isArray(data.items)
            || data.items.length > bounded
        ) {
            throw new Error('concierge-task-centre-invalid');
        }

        return data.items.flatMap(item => {
            if (!item || typeof item !== 'object' || Array.isArray(item)) return [];
            const requestId = String(item.request_id || '');
            const status = String(item.status || '');
            const capabilities = Array.isArray(item.requested_capabilities)
                ? item.requested_capabilities.map(value => String(value)).slice(0, 20)
                : [];
            if (!UUID.test(requestId) || !status || capabilities.length > 20) return [];

            const receipt = item.cancellation_receipt;
            const receiptIntegrity = item.cancellation_receipt_integrity == null
                ? null
                : String(item.cancellation_receipt_integrity);
            if (
                receipt != null
                && (
                    typeof receipt !== 'object'
                    || Array.isArray(receipt)
                    || receipt.integrity !== 'verified'
                    || !SHA256.test(String(receipt.receipt_sha256 || ''))
                    || String(receipt.request_id || '') !== requestId
                )
            ) {
                return [];
            }

            const retirement = item.retirement_receipt;
            const retirementIntegrity = item.retirement_receipt_integrity == null
                ? null
                : String(item.retirement_receipt_integrity);
            if (
                retirement != null
                && (
                    typeof retirement !== 'object'
                    || Array.isArray(retirement)
                    || retirement.integrity !== 'verified'
                    || !SHA256.test(String(retirement.receipt_sha256 || ''))
                    || String(retirement.request_id || '') !== requestId
                    || retirement.execution_started !== false
                    || Number(retirement.specialist_checkpoint_count || 0) !== 0
                    || Number(retirement.retry_count || 0) !== 0
                )
            ) {
                return [];
            }

            const projected = {
                requestId,
                status,
                requestedCapabilities: capabilities,
                clientName: String(item.client_name || ''),
                purpose: String(item.purpose || ''),
                requestedAt: item.requested_at || null,
                waitingOn: String(item.waiting_on || ''),
                attentionRequired: item.attention_required === true,
                attentionReason: String(item.attention_reason || ''),
                canCancel: item.can_cancel === true,
                supersededByRequestId: item.superseded_by_request_id
                    ? String(item.superseded_by_request_id)
                    : null,
                cancellationReceiptIntegrity: receiptIntegrity,
                cancellationReceipt: receipt || null,
                retirementReceiptIntegrity: retirementIntegrity,
                retirementReceipt: retirement || null,
                planTtl: item.plan_ttl || null,
            };
            projected.cancellationText = cancellationReceiptText(item);
            projected.retirementText = retirementReceiptText(item);
            projected.planTtlText = planTtlText(item);
            return [projected];
        });
    }

    async function consumeOne() {
        if (!accountReady() || document.visibilityState === 'hidden') return false;

        const conversationId = activeConversationId();
        if (!conversationId) return false;

        const event = await requestJson('/foundation/completions/claim', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({conversation_id: conversationId}),
        });
        if (event.available !== true) return false;

        const eventId = String(event.eventId || '');
        const leaseToken = String(event.leaseToken || '');
        const eventType = String(event.eventType || '');
        if (!UUID.test(eventId) || !UUID.test(leaseToken)) {
            throw new Error('completion-lease-invalid');
        }

        if (eventType === 'retry-completed') {
            const verified = await verifiedAnswer(event, conversationId);
            render(eventId, eventType, verified.displayText);
            const sourceMessageId = String(event.sourceMessageId || event.requestId || '');
            if (UUID.test(sourceMessageId) && typeof window.clearPendingRequest === 'function') {
                try { window.clearPendingRequest(sourceMessageId); } catch (_) {}
            }
        } else if (eventType === 'retry-abandoned') {
            if (String(event.sourceConversationId || '') !== conversationId) {
                throw new Error('completion-conversation-binding-mismatch');
            }
            render(
                eventId,
                eventType,
                'That delayed specialist work could not be completed, so I have not filled in the missing result. You can ask me to try the request again.',
            );
        } else {
            throw new Error('completion-event-invalid');
        }

        await acknowledge(eventId, leaseToken);
        return true;
    }

    async function poll() {
        if (inFlight || !accountReady() || document.visibilityState === 'hidden') return;
        inFlight = (async () => {
            try {
                // Drain a small bounded batch without hammering the server.
                for (let count = 0; count < 3; count += 1) {
                    const consumed = await consumeOne();
                    if (!consumed) break;
                }
            } catch (_) {
                // Lease expiry and the next poll provide recovery. Do not surface
                // unverified data or acknowledge an event that was not rendered.
            } finally {
                inFlight = null;
            }
        })();
        return inFlight;
    }

    function schedule() {
        if (timer !== null) clearInterval(timer);
        timer = setInterval(() => void poll(), POLL_MS);
    }

    document.addEventListener('DOMContentLoaded', schedule);
    window.addEventListener('l-account-ready', () => {
        schedule();
        void poll();
    });
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') void poll();
    });
    window.addEventListener('online', () => void poll());

    window.lConciergeCompletions = {
        refresh: () => poll(),
        history: (limit = 100) => delayedHistory(limit),
        pending: (limit = 100) => pendingJobs(limit),
        jobs: (limit = 50) => taskCentre(limit),
        cancel: requestId => cancelPending(requestId),
    };
})();

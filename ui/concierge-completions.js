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

    async function verifiedAnswer(event) {
        const answer = typeof event.finalAnswer === 'string' ? event.finalAnswer.trim() : '';
        const declared = String(event.finalAnswerSha256 || '');
        if (!answer || answer.length > 50000 || !SHA256.test(declared)) {
            throw new Error('completion-answer-invalid');
        }
        if (typeof window.sha256HexText !== 'function') {
            throw new Error('completion-hash-verifier-unavailable');
        }
        const actual = await window.sha256HexText(answer);
        if (actual !== declared) {
            throw new Error('completion-answer-integrity-mismatch');
        }
        return answer;
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

    async function consumeOne() {
        if (!accountReady() || document.visibilityState === 'hidden') return false;

        const event = await requestJson('/foundation/completions/claim', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: '{}',
        });
        if (event.available !== true) return false;

        const eventId = String(event.eventId || '');
        const leaseToken = String(event.leaseToken || '');
        const eventType = String(event.eventType || '');
        if (!UUID.test(eventId) || !UUID.test(leaseToken)) {
            throw new Error('completion-lease-invalid');
        }

        if (eventType === 'retry-completed') {
            const answer = await verifiedAnswer(event);
            render(eventId, eventType, answer);
        } else if (eventType === 'retry-abandoned') {
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
    };
})();

/* Owner-authenticated live Concierge fleet status. No specialist endpoints or grant ids reach the browser. */
(() => {
    let inFlight = null;
    let lastLoadedAt = 0;
    const CACHE_MS = 30000;

    const el = id => document.getElementById(id);

    function renderUnavailable(message) {
        const summary = el('specialistFleetSummary');
        const status = el('specialistFleetStatus');
        const list = el('specialistFleetList');
        if (summary) summary.textContent = '— unavailable';
        if (status) status.textContent = message || 'Specialist status is temporarily unavailable.';
        if (list) list.replaceChildren();
    }

    function renderFleet(fleet) {
        const summary = el('specialistFleetSummary');
        const status = el('specialistFleetStatus');
        const list = el('specialistFleetList');
        if (!summary || !status || !list) return;

        const total = Number(fleet?.specialist_count || 0);
        const ready = Number(fleet?.executable_count || 0);
        const blocked = Number(fleet?.blocked_count || 0);
        summary.textContent = `— ${ready}/${total} ready`;
        summary.className = blocked === 0 ? 'specialist-ready' : 'specialist-blocked';
        status.textContent = blocked === 0
            ? `Concierge fleet healthy — ${ready} specialists ready.`
            : `Concierge fleet degraded — ${blocked} specialist${blocked === 1 ? '' : 's'} blocked.`;

        list.replaceChildren();
        const specialists = Array.isArray(fleet?.specialists) ? fleet.specialists : [];
        for (const item of specialists) {
            if (!item || typeof item !== 'object') continue;
            const row = document.createElement('div');
            row.className = 'specialist-fleet-row';
            const title = document.createElement('strong');
            title.textContent = String(item.app_name || item.display_name || item.capability_id || 'Specialist');
            const state = document.createElement('span');
            state.className = item.executable ? 'specialist-ready' : 'specialist-blocked';
            state.textContent = item.executable ? 'Ready' : 'Unavailable';
            title.append(' — ', state);

            const capability = document.createElement('small');
            capability.textContent = String(item.display_name || item.capability_id || '');

            const reason = document.createElement('small');
            reason.textContent = item.executable
                ? 'Live runtime, active adapter, matching consent and Companion grant.'
                : 'Reason: ' + String(item.reason_code || item.runtime_reason_code || 'unavailable');

            row.append(title, capability, reason);
            list.append(row);
        }
    }

    async function loadFleet(force = false) {
        if (document.documentElement.dataset.account !== 'ready') return;
        if (!force && Date.now() - lastLoadedAt < CACHE_MS) return;
        if (inFlight) return inFlight;
        const status = el('specialistFleetStatus');
        if (status) status.textContent = 'Checking live specialist status…';

        inFlight = (async () => {
            try {
                const response = await fetch('/foundation/fleet', {
                    method: 'GET',
                    cache: 'no-store',
                    signal: AbortSignal.timeout(10000)
                });
                const data = await response.json();
                if (!response.ok || !data || typeof data !== 'object') {
                    throw new Error('fleet-status-unavailable');
                }
                renderFleet(data);
                lastLoadedAt = Date.now();
            } catch (_) {
                renderUnavailable('Could not verify the live specialist fleet. L will not treat an unverified specialist as ready.');
            } finally {
                inFlight = null;
            }
        })();
        return inFlight;
    }

    document.addEventListener('DOMContentLoaded', () => {
        el('refreshSpecialists')?.addEventListener('click', () => loadFleet(true));
    });
    window.addEventListener('l-account-ready', () => loadFleet(true));
    window.addEventListener('l-specialists-opened', () => loadFleet(false));
    window.lFoundationFleet = { refresh: () => loadFleet(true) };
})();

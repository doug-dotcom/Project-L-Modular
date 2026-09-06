/* Sign-in tokens stay in this tab; only same-origin API requests receive them. */
(() => {
    const nativeFetch = window.fetch.bind(window);
    const key = 'l-account-session-v1';
    let session = null, refreshing = null;
    let resolveReady;
    const ready = new Promise(resolve => { resolveReady = resolve; });
    const persist = value => {
        session = value;
        try { if (value) sessionStorage.setItem(key, JSON.stringify(value)); else sessionStorage.removeItem(key); } catch (_) {}
    };
    try { session = JSON.parse(sessionStorage.getItem(key) || 'null'); } catch (_) {}
    function locked(message) {
        document.documentElement.dataset.account = 'locked';
        window.lVoice?.background();
        const status = document.getElementById('accountStatus');
        if (status) status.textContent = message || 'Sign in to your private L.';
    }
    async function call(path, body) {
        const response = await nativeFetch(path, {method: 'POST', cache: 'no-store',
            headers: {'Content-Type':'application/json'}, body: JSON.stringify(body), signal: AbortSignal.timeout(20000)});
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Check the form and try again.');
        return result;
    }
    async function access() {
        if (!session?.access_token) return null;
        if ((session.expires_at || 0) * 1000 > Date.now() + 60000) return session.access_token;
        if (!refreshing) refreshing = call('/account/refresh', {refresh_token:session.refresh_token})
            .then(value => { persist({...value, expires_at:Math.floor(Date.now()/1000)+value.expires_in}); return value.access_token; })
            .catch(error => { locked('Session refresh failed. Sign in again, or retry when connected.'); throw error; })
            .finally(() => { refreshing = null; });
        return refreshing;
    }
    window.fetch = async (input, options = {}) => {
        const url = new URL(typeof input === 'string' ? input : input.url, location.href);
        if (url.origin !== location.origin || url.pathname.startsWith('/ui/') || url.pathname === '/health') {
            return nativeFetch(input, options);
        }
        await ready;
        const token = await access();
        if (!token) { locked(); return new Response(JSON.stringify({detail:'Please sign in to L.'}), {status:401, headers:{'Content-Type':'application/json'}}); }
        const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
        headers.set('Authorization', 'Bearer ' + token);
        const response = await nativeFetch(input, {...options, headers, cache:'no-store'});
        if (response.status === 401 || response.status === 403) locked('Please sign in to your authorised L account.');
        return response;
    };
    async function verify() {
        const token = await access();
        if (!token) { locked(); return false; }
        const response = await nativeFetch('/account/me', {headers:{Authorization:'Bearer '+token}, cache:'no-store'});
        if (!response.ok) { locked('Sign in to your authorised L account.'); return false; }
        const user = await response.json();
        document.documentElement.dataset.account = 'ready';
        document.getElementById('accountLabel').textContent = '— signed in';
        window.dispatchEvent(new CustomEvent('l-account-ready', {detail:{user_id:user.user_id}}));
        return true;
    }
    document.addEventListener('DOMContentLoaded', async () => {
        const gate = document.createElement('section');
        gate.id = 'accountGate';
        gate.innerHTML = '<h1>Sign in to L</h1><p>Your private companion and saved files.</p>' +
            '<form id="accountForm"><label>Email<input id="accountEmail" type="email" autocomplete="username" required></label>' +
            '<label>Password<input id="accountPassword" type="password" autocomplete="current-password" minlength="8" maxlength="256" required></label>' +
            '<button type="submit">Sign in</button><button id="createLAccount" type="button">Create my L login</button></form>' +
            '<p id="accountStatus" role="status" aria-live="polite">Use the email chosen for your L account. A new password needs at least 12 characters.</p>';
        document.body.appendChild(gate);
        document.getElementById('accountFallback')?.remove?.();
        async function submit(signup) {
            const form = document.getElementById('accountForm');
            if (!form.reportValidity()) return;
            const password = document.getElementById('accountPassword');
            const buttons = [...form.querySelectorAll('button')];
            buttons.forEach(button => { button.disabled = true; });
            try {
                const result = await call('/account/' + (signup ? 'signup' : 'login'), {
                    email:document.getElementById('accountEmail').value, password:password.value});
                password.value = '';
                if (result.confirmation_required) {
                    locked('Check your email to confirm your account, then return to this page and sign in.');
                } else {
                    persist({...result, expires_at:Math.floor(Date.now()/1000)+result.expires_in});
                    await verify();
                }
            } catch (error) { locked(error.message); }
            finally { buttons.forEach(button => { button.disabled = false; }); }
        }
        document.getElementById('accountForm').onsubmit = event => { event.preventDefault(); submit(false); };
        document.getElementById('createLAccount').onclick = () => submit(true);
        document.getElementById('signOutL').onclick = async () => {
            try {
                const response = await window.fetch('/account/logout', {method:'POST'});
                if (!response.ok) throw new Error('Sign-out could not be confirmed. Please retry when connected.');
                persist(null); location.reload();
            } catch (error) { document.getElementById('evidenceStatus').textContent = error.message; }
        };
        try { await verify(); } catch (_) { locked('Could not verify your session. Sign in when connected.'); }
        finally { resolveReady(); }
    });
})();

const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const html = fs.readFileSync('ui/index.html', 'utf8');
const main = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).find(s => s.includes('const API_URL'));
const scenario = process.argv[2], storage = new Map(), requests = [], timers = new Map(), elements = new Map(), domReady = [];
const pendingKey = 'l-evidence-pending', crypto = require('node:crypto').webcrypto;
let now = 0, timerId = 0, polls = 0, phase = 'initial', latePoll, aborted = 0;
const ready = {status: 'ready', result: {reply: 'Recovered file answer'}};
const unresolved = ['pending', 'pending_again', 'history_cleanup', 'stalled_poll', 'stalled_body'].includes(scenario);
function element() {
    return {value: '', textContent: '', disabled: false, children: [],
        replaceChildren(...nodes) {this.children = nodes;}, appendChild(node) {this.children.push(node);}, add(node) {this.children.push(node);}};
}
const el = id => {if (!elements.has(id)) elements.set(id, element()); return elements.get(id);};
const context = {
    AbortController, crypto, performance: {now: () => now},
    window: {addEventListener() {}, lVoice: {onReply() {if (scenario === 'voice_failure') throw Error('PRIVATE voice error');}}},
    document: {documentElement:{dataset:{account:'ready'}}, addEventListener(name, fn) {if (name === 'DOMContentLoaded') domReady.push(fn);}, getElementById: el, createElement: element},
    MutationObserver: class {observe() {}},
    Option: class {constructor(text, value) {this.text = text; this.value = value;}},
    sessionStorage: {
        getItem: key => storage.get(key) ?? null,
        setItem: (key, value) => storage.set(key, value),
        removeItem(key) {if (scenario === 'cleanup_failure') throw Error('PRIVATE cleanup error'); storage.delete(key);}
    },
    setTimeout(fn, delay) {const id = ++timerId; timers.set(id, {fn, at: now + delay}); return id;},
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options = {}) => {
        requests.push({url, options});
        options.signal?.addEventListener('abort', () => aborted++);
        const response = value => ({ok: true, json: async () => value});
        if (url === '/evidence/files/doc') return response({id: 'doc', page_count: 1, pages: [{text: 'File page text'}]});
        if (url === '/evidence/ask') {
            if (scenario === 'lost_ack') throw Error('PRIVATE acknowledgement error');
            if (scenario === 'stalled_ack') return new Promise(() => {});
            return response({status: 'queued'});
        }
        if (url === '/evidence/tasks') {
            const body = JSON.parse(requests.find(r => r.url === '/evidence/ask').options.body);
            return response({tasks: [{request_id: body.request_id, status: 'ready', request: {question: body.question}}]});
        }
        assert.ok(url.startsWith('/evidence/tasks/'), url);
        assert.equal(options.cache, 'no-store'); polls++;
        if (scenario === 'stalled_poll') return new Promise(resolve => {latePoll = () => resolve(response(ready));});
        if (scenario === 'stalled_body') return {ok: true, json: () => new Promise(() => {})};
        if (scenario === 'transient_poll' && polls === 1) throw Error('PRIVATE transient read failure');
        if (scenario === 'newer_pending') storage.set(pendingKey, JSON.stringify({request_id: 'newer-question'}));
        return response(unresolved && phase === 'initial' ? {status: 'running'} : ready);
    }
};
vm.createContext(context); vm.runInContext(main, context);
vm.runInContext(fs.readFileSync('ui/evidence.js', 'utf8'), context);
domReady.at(-1)();
async function drive(promise) {
    let done = false, failure;
    promise.then(() => {done = true;}, error => {failure = error; done = true;});
    for (let step = 0; step < 500 && !done; step++) {
        await new Promise(setImmediate);
        if (done) break;
        const entry = [...timers.entries()].sort((a, b) => a[1].at - b[1].at)[0];
        assert.ok(entry, 'File recovery stalled without a timer');
        timers.delete(entry[0]); now = entry[1].at; entry[1].fn();
    }
    assert.ok(done, 'File recovery exceeded its bounded wait');
    if (failure) throw failure;
}
(async () => {
    el('evidenceFiles').value = 'doc'; await el('evidenceFiles').onchange();
    el('evidenceQuestion').value = 'My file question';
    await drive(el('askEvidence').onclick());
    const posts = () => requests.filter(r => r.url === '/evidence/ask');
    assert.equal(posts().length, 1);
    const first = JSON.parse(posts()[0].options.body), id = first.request_id;
    assert.equal(first.document_id, 'doc'); assert.equal(first.page, 1); assert.equal(first.question, 'My file question');
    assert.ok(requests.filter(r => r.url.startsWith('/evidence/tasks/')).every(r => r.url.endsWith(id)));
    assert.equal(el('askEvidence').disabled, false); assert.equal(el('evidenceQuestion').value, 'My file question');
    assert.equal(timers.size, 0); assert.ok(now <= 135000);
    assert.ok(!el('evidenceStatus').textContent.includes('PRIVATE'));
    if (unresolved) {
        assert.ok(now <= 120000); assert.equal(JSON.parse(storage.get(pendingKey)).request_id, id);
        assert.match(el('evidenceStatus').textContent, /stopped waiting/);
        assert.match(el('evidenceStatus').textContent, /Saved file answers/);
        assert.equal(el('evidenceAnswer').textContent, '');
    } else {
        assert.equal(el('evidenceAnswer').textContent, ready.result.reply);
        assert.match(el('evidenceStatus').textContent, /Answer recovered/);
        assert.equal(storage.has(pendingKey), ['cleanup_failure', 'newer_pending'].includes(scenario));
        if (scenario === 'newer_pending') assert.equal(JSON.parse(storage.get(pendingKey)).request_id, 'newer-question');
    }
    if (['stalled_ack', 'stalled_poll', 'stalled_body'].includes(scenario)) assert.ok(aborted > 0);
    if (scenario === 'transient_poll') assert.equal(polls, 2);
    if (scenario === 'pending_again') {
        phase = 'ready'; await drive(el('askEvidence').onclick());
        assert.equal(posts().length, 2); assert.equal(JSON.parse(posts()[1].options.body).request_id, id);
        assert.equal(storage.has(pendingKey), false); assert.equal(el('evidenceAnswer').textContent, ready.result.reply);
    }
    if (scenario === 'history_cleanup') {
        phase = 'ready'; await el('evidenceHistory').onclick();
        await drive(el('evidenceTasks').children[0].onclick());
        assert.equal(posts().length, 1); assert.equal(storage.has(pendingKey), false);
        assert.equal(el('evidenceAnswer').textContent, ready.result.reply);
    }
    if (latePoll) {
        const text = el('evidenceStatus').textContent, count = requests.length;
        latePoll(); await new Promise(setImmediate);
        assert.equal(el('evidenceStatus').textContent, text); assert.equal(el('evidenceAnswer').textContent, '');
        assert.equal(requests.length, count);
    }
    assert.equal(timers.size, 0);
})().catch(error => {console.error(error); process.exitCode = 1;});

const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const html = fs.readFileSync('ui/index.html', 'utf8');
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const scenario = process.argv[2], storage = new Map(), requests = [], messages = [], timers = new Map();
let now = 0, timerId = 0, aborted = 0, lateAck, blockWrites = false;
const file = {name: 'picture.jpg'}, input = {value: 'My picture question'}, fileInput = {value: 'selected-picture'};
const chat = {scrollHeight: 10, appendChild() {}};
const ready = {status: 'ready', result: {reply: 'Recovered picture answer'}};
const rejected = {rejected_type: 'unsupported_file', rejected_size: 'invalid_file_size', rejected_id: 'invalid_request_id'};
const context = {
    AbortController, TextEncoder, performance: {now: () => now},
    window: {crypto: require('node:crypto').webcrypto},
    document: {addEventListener() {}, createElement: () => ({style: {}}), getElementById: id => id === 'message' ? input : id === 'fileInput' ? fileInput : chat},
    URL: {createObjectURL: () => 'blob:fixture'},
    FormData: class {constructor() {this.fields = {};} append(k, v) {this.fields[k] = v;}},
    localStorage: {
        getItem: key => storage.get(key) ?? null,
        setItem(k, v) {if (blockWrites) throw Error('PRIVATE storage error'); storage.set(k, v);},
        removeItem(k) {if (blockWrites) throw Error('PRIVATE storage error'); storage.delete(k);}
    },
    setTimeout(fn, delay) {const id = ++timerId; timers.set(id, {fn, at: now + delay}); return id;},
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options) => {
        requests.push({url, options});
        options.signal.addEventListener('abort', () => aborted++);
        if (options.method === 'POST') {
            if (['lost_ack', 'unresolved'].includes(scenario)) throw Error('PRIVATE network error');
            if (scenario === 'late_ack') return new Promise(resolve => {lateAck = resolve;});
            if (scenario === 'stalled_body') return {ok: true, json: () => new Promise(() => {})};
            return {ok: true, json: async () => ({status: rejected[scenario] || 'pending', message: 'PRIVATE server detail'})};
        }
        if (scenario === 'cleanup_failure') blockWrites = true;
        return {ok: true, json: async () => ['unresolved', 'no_double_wait'].includes(scenario) ? {status: 'pending'} : ready};
    }
};
vm.createContext(context);
vm.runInContext(scripts.find(s => s.includes('const API_URL')), context);
vm.runInContext(scripts.find(s => s.includes('async function submitImage')), context);
context.appendChatMessage = (parent, role, text) => {const m = {role, textContent: text, remove() {this.removed = true;}}; messages.push(m); return m;};
async function drive(promise) {
    let done = false, failure;
    promise.then(() => {done = true;}, error => {failure = error; done = true;});
    for (let step = 0; step < 500 && !done; step++) {
        await new Promise(setImmediate);
        if (done) break;
        const entry = [...timers.entries()].sort((a, b) => a[1].at - b[1].at)[0];
        assert.ok(entry, 'Upload stalled without a recovery timer');
        timers.delete(entry[0]); now = entry[1].at; entry[1].fn();
    }
    assert.ok(done, 'Upload exceeded its bounded wait');
    if (failure) throw failure;
}
(async () => {
    await drive(context.submitImage(file));
    const uploads = requests.filter(r => r.options.method === 'POST'), polls = requests.filter(r => r.options.method !== 'POST');
    assert.equal(uploads.length, 1); assert.equal(uploads[0].url, '/image/start');
    const fields = uploads[0].options.body.fields, saved = JSON.parse(storage.get('project-l-saved-tasks'))[0];
    assert.equal(fields.file, file); assert.equal(fields.prompt, 'My picture question');
    assert.equal(fields.request_id, saved.requestId);
    assert.ok(polls.every(r => r.url.endsWith(saved.requestId)));
    assert.ok(requests.every(r => r.options.headers['X-L-Recovery-Token'] === storage.get('project-l-recovery-token')));
    assert.equal(input.value, ''); assert.equal(fileInput.value, '');
    assert.equal(messages.filter(m => m.role === 'user').length, 1);
    assert.ok(messages.slice(1, -1).every(m => m.removed));
    assert.ok(messages.every(m => !m.textContent.includes('PRIVATE')));
    assert.equal(timers.size, 0); assert.ok(now <= 135000);
    if (rejected[scenario]) {
        assert.equal(polls.length, 0); assert.equal(saved.pending, false);
        assert.equal(storage.has('project-l-pending-request'), false);
        assert.equal(messages.at(-1).role, 'assistant error');
        assert.match(messages.at(-1).textContent, /Please/);
    } else if (['unresolved', 'no_double_wait'].includes(scenario)) {
        assert.ok(polls.length > 0); assert.ok(now <= 120000);
        assert.equal(saved.pending, true); assert.equal(storage.has('project-l-pending-request'), true);
        assert.match(messages.at(-1).textContent, /Check Saved answers before uploading/);
    } else {
        assert.equal(polls.length, 1); assert.equal(messages.at(-1).textContent, ready.result.reply);
        assert.equal(saved.pending, scenario === 'cleanup_failure');
        assert.equal(storage.has('project-l-pending-request'), scenario === 'cleanup_failure');
    }
    if (['stalled_body', 'late_ack'].includes(scenario)) assert.equal(aborted, 1);
    if (lateAck) {
        const before = messages.length;
        lateAck({ok: true, json: async () => ({status: 'pending'})});
        await new Promise(setImmediate);
        assert.equal(messages.length, before); assert.equal(requests.length, 2);
    }
})().catch(error => {console.error(error); process.exitCode = 1;});

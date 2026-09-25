const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const html = fs.readFileSync('ui/index.html', 'utf8');
const source = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).find(s => s.includes('const API_URL'));
const scenario = process.argv[2], key = 'project-l-saved-tasks', pendingKey = 'project-l-pending-request';
const originals = {json: '[{"requestId":"older"},', empty: '', null: 'null', object: '{"requestId":"older"}', scalar: '42'};
const older = [{requestId: 'older', message: 'Keep this question', pending: true, extra: 'retain'}];
const initial = Object.hasOwn(originals, scenario) ? originals[scenario] : JSON.stringify(older);
const pointer = JSON.stringify({requestId: 'older', message: 'Keep this question'});
const storage = new Map([[key, initial], [pendingKey, pointer], ['project-l-recovery-token', 'a'.repeat(64)]]);
if (scenario === 'missing') storage.delete(key);
let readBlocked = scenario === 'read_failure', recoveries = 0;
const writes = [], requests = [], messages = [], spoken = [];
const draft = '  Keep my exact draft\nwith spacing 👊  ';
const input = {value: draft, focus() { this.focused = true; }}, chat = {scrollHeight: 10};
const context = {
    window: {crypto: require('node:crypto').webcrypto, lVoice: {canSend: () => true, saveDraft() {}, onReply: text => spoken.push(text)}},
    document: {addEventListener() {}, getElementById: id => id === 'message' ? input : chat},
    localStorage: {
        getItem(k) { if (readBlocked && k === key) throw Error('PRIVATE read failure'); return storage.get(k) ?? null; },
        setItem(k, value) { writes.push(k); storage.set(k, value); },
        removeItem(k) { writes.push(k); storage.delete(k); }
    }
};
vm.createContext(context); vm.runInContext(source, context);
context.appendChatMessage = (parent, role, text) => { const m = {role, text, remove() {}}; messages.push(m); return m; };
context.fetchChatJson = async (url, options) => { requests.push({url, options}); return {status: 'queued'}; };
context.recoverChatResponse = async () => {
    recoveries++;
    if (scenario === 'live_corrupt') storage.set(key, originals.json);
    if (scenario === 'live_read_failure') readBlocked = true;
    writes.length = 0;
    return {reply: 'Delivered answer'};
};
(async () => {
    if (scenario.startsWith('live_')) {
        await context.sendMessage();
        assert.equal(requests.length, 1); assert.equal(recoveries, 1);
        assert.equal(messages.at(-1).text, 'Delivered answer'); assert.deepEqual(spoken, ['Delivered answer']);
        assert.equal(messages.filter(m => m.role === 'assistant error').length, 0);
        assert.deepEqual(writes, []);
        const id = JSON.parse(requests[0].options.body).request_id;
        assert.equal(JSON.parse(storage.get(pendingKey)).requestId, id);
        if (scenario === 'live_corrupt') assert.equal(storage.get(key), originals.json);
        else assert.ok(JSON.parse(storage.get(key)).some(t => t.requestId === id && t.pending));
        return;
    }
    if (scenario === 'valid' || scenario === 'missing') {
        context.rememberPendingRequest('new', 'New question');
        assert.equal(context.clearPendingRequest('new'), true);
        const expected = scenario === 'valid' ? [...older] : [];
        expected.push({requestId: 'new', message: 'New question', kind: 'chat', pending: false});
        assert.deepEqual(JSON.parse(storage.get(key)), expected);
        assert.equal(storage.has(pendingKey), false);
        return;
    }
    // Read-only views remain safe; both write paths must preserve the source.
    assert.doesNotThrow(() => context.savedTasks());
    assert.throws(() => context.rememberPendingRequest('new', 'New question'));
    assert.equal(context.clearPendingRequest('older'), false);
    await context.sendMessage();
    assert.equal(input.value, draft); assert.equal(input.focused, true);
    assert.equal(requests.length, 0); assert.equal(recoveries, 0);
    assert.match(messages.at(-1).text, /has not been sent/);
    assert.ok(!messages.at(-1).text.includes('PRIVATE'));
    assert.deepEqual(writes, []);
    assert.equal(storage.get(key), initial); assert.equal(storage.get(pendingKey), pointer);
})().catch(err => { console.error(err); process.exitCode = 1; });

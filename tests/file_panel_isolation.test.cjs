const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const scenario = process.argv[2], elements = new Map(), events = {}, requests = [], voices = [], storage = new Map();
const root = {dataset: {account: 'ready'}}, pendingKey = 'l-evidence-pending';
let initialise, mutation, downloadCount = 0;
function element() {return {value: '', textContent: '', disabled: false, children: [],
    appendChild(n) {this.children.push(n);}, replaceChildren(...n) {this.children = n;}, add(n) {this.children.push(n);}, click() {}, remove() {}};}
function el(id) {if (!elements.has(id)) elements.set(id, element()); return elements.get(id);}
const response = value => ({ok: true, json: async () => value});
const doc = id => ({id, filename: id + '.pdf', page_count: 2, pages: [{text: id + ' page one'}, {text: id + ' page two'}]});
const ready = text => ({status: 'ready', result: {reply: text}});
const deferred = () => {let resolve, reject; const promise = new Promise((yes, no) => {resolve = yes; reject = no;}); return {promise, resolve, reject};};
const tasks = ['old', 'new'].map(id => ({request_id: id, status: 'ready', request: {question: id + ' question'}}));
let fetchHandler = async url => {
    if (url === '/evidence/files') return response({files: [{id: 'doc', filename: 'doc.pdf', page_count: 2}]});
    if (url === '/evidence/tasks') return response({tasks});
    if (url.startsWith('/evidence/files/')) return response(doc(url.split('/').at(-1)));
    throw Error('Unexpected API ' + url);
};
let answerHandler = async url => url === '/evidence/ask' ? {status: 'queued'} : ready('Current answer');
const context = {
    AbortController, setTimeout, clearTimeout,
    crypto: require('node:crypto').webcrypto, performance: {now: () => 0},
    window: {addEventListener: (name, fn) => {events[name] = fn;}, lVoice: {canSend: () => true, onReply: text => voices.push(text)}},
    document: {documentElement: root, addEventListener(name, fn) {initialise = fn;}, getElementById: el, createElement: element, body: element()},
    MutationObserver: class {constructor(fn) {mutation = fn;} observe() {}},
    Option: class {constructor(text, value) {this.text = text; this.value = value;}},
    FormData: class {append() {}},
    URL: {createObjectURL() {downloadCount++; return 'blob:fixture';}, revokeObjectURL() {}},
    sessionStorage: {getItem: key => storage.get(key) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: key => storage.delete(key)},
    fetch: (url, options = {}) => {requests.push({url, options}); return fetchHandler(url, options);},
    fetchChatJson: (url, options = {}) => {requests.push({url, options}); return answerHandler(url, options);}
};
vm.createContext(context); vm.runInContext(fs.readFileSync('ui/evidence.js', 'utf8'), context); initialise();
const flush = async () => {for (let i = 0; i < 10; i++) await Promise.resolve();};
const choose = async id => {el('evidenceFiles').value = id; await el('evidenceFiles').onchange();};
const lock = () => {root.dataset.account = 'locked'; mutation();};
const signIn = async () => {root.dataset.account = 'ready'; await events['l-account-ready']();};
const ask = () => {el('evidenceQuestion').value = 'My question'; return el('askEvidence').onclick();};
const polls = () => requests.filter(r => r.url.startsWith('/evidence/tasks/'));
(async () => {
    await choose('doc');
    if (scenario === 'history_order') {
        await el('evidenceHistory').onclick(); const controls = el('evidenceTasks').children, old = deferred();
        storage.set(pendingKey, JSON.stringify({request_id: 'old'}));
        answerHandler = url => url.endsWith('/old') ? old.promise : Promise.resolve(ready('New answer'));
        const first = controls[0].onclick(); await controls[1].onclick();
        old.resolve(ready('Old answer')); await first;
        assert.equal(el('evidenceAnswer').textContent, 'New answer'); assert.deepEqual(voices, ['New answer']);
        assert.equal(JSON.parse(storage.get(pendingKey)).request_id, 'old'); return;
    }
    if (scenario === 'old_finally') {
        const old = deferred(), current = deferred(); let starts = 0;
        answerHandler = url => url === '/evidence/ask' ? (++starts === 1 ? old.promise : current.promise) : Promise.resolve(ready('New session answer'));
        const first = ask(); await flush(); await signIn(); await choose('newdoc');
        const second = ask(); await flush(); assert.equal(el('askEvidence').disabled, true);
        const newPending = storage.get(pendingKey);
        old.resolve({status: 'queued'}); await first;
        assert.equal(el('askEvidence').disabled, true); assert.equal(storage.get(pendingKey), newPending); assert.equal(polls().length, 0);
        current.resolve({status: 'queued'}); await second;
        assert.equal(el('askEvidence').disabled, false); assert.equal(el('evidenceAnswer').textContent, 'New session answer');
        assert.deepEqual(voices, ['New session answer']); return;
    }
    if (['selection', 'page', 'locked_reply', 'account_switch', 'late_ack'].includes(scenario)) {
        const late = deferred();
        answerHandler = url => (scenario === 'late_ack' ? url === '/evidence/ask' : url !== '/evidence/ask') ? late.promise : Promise.resolve({status: 'queued'});
        const pending = ask(); await flush(); const saved = storage.get(pendingKey);
        if (scenario === 'page') {el('evidencePage').value = 2; el('evidencePage').onchange();}
        else if (scenario === 'locked_reply') lock();
        else if (scenario === 'account_switch') await signIn();
        else await choose('newdoc');
        const status = el('evidenceStatus').textContent;
        late.resolve(scenario === 'late_ack' ? {status: 'queued'} : ready('Old answer')); await pending;
        assert.equal(el('evidenceAnswer').textContent, ''); assert.equal(el('evidenceStatus').textContent, status);
        assert.deepEqual(voices, []); assert.equal(storage.get(pendingKey), saved);
        if (scenario === 'late_ack') assert.equal(polls().length, 0);
        if (scenario === 'selection') assert.equal(el('evidencePreview').textContent, 'newdoc page one');
        if (scenario === 'page') assert.equal(el('evidencePreview').textContent, 'doc page two');
        if (scenario === 'locked_reply') {
            const before = requests.length;
            await el('askEvidence').onclick(); await el('evidenceHistory').onclick(); await el('refreshFiles').onclick();
            await el('openOriginal').onclick(); await context.window.lEvidenceUpload({size: 1});
            assert.equal(requests.length, before); assert.equal(el('evidencePreview').textContent, '');
            assert.equal(el('evidenceQuestion').value, ''); assert.equal(el('evidenceTasks').children.length, 0);
        }
        return;
    }
    if (scenario === 'choose_race_error') {
        const late = deferred(), original = fetchHandler;
        fetchHandler = url => url.endsWith('/older') ? late.promise : original(url);
        const first = choose('older'); await choose('newdoc');
        late.reject(Error('Old selection error')); await first;
        assert.equal(el('evidencePreview').textContent, 'newdoc page one'); assert.equal(el('evidenceStatus').textContent, ''); return;
    }
    if (['refresh_selection', 'refresh_selection_error'].includes(scenario)) {
        const late = deferred(), original = fetchHandler;
        fetchHandler = url => url === '/evidence/files' ? late.promise : original(url);
        const pending = el('refreshFiles').onclick(); await choose('newdoc');
        if (scenario === 'refresh_selection_error') late.reject(Error('Old list error'));
        else late.resolve(response({files: []}));
        await pending;
        assert.equal(el('evidenceStatus').textContent, '');
        assert.equal(el('evidenceFiles').value, 'newdoc'); assert.equal(el('evidencePreview').textContent, 'newdoc page one'); return;
    }
    const late = deferred(); let pending, original = fetchHandler;
    if (scenario.startsWith('list_')) {
        fetchHandler = url => url === '/evidence/files' ? late.promise : original(url);
        pending = el('refreshFiles').onclick();
    } else if (scenario === 'preview_after_lock') {
        fetchHandler = () => late.promise; pending = choose('older');
    } else if (scenario === 'history_after_lock') {
        fetchHandler = () => late.promise; pending = el('evidenceHistory').onclick();
    } else if (scenario === 'upload_after_lock') {
        fetchHandler = () => late.promise; pending = context.window.lEvidenceUpload({size: 1});
    } else if (scenario === 'download_after_lock') {
        fetchHandler = async () => ({ok: true, blob: () => late.promise}); pending = el('openOriginal').onclick();
    } else throw Error('Unknown scenario ' + scenario);
    await flush(); lock(); fetchHandler = original;
    if (scenario === 'list_after_switch') await signIn();
    const before = requests.length, state = JSON.stringify([...elements]);
    const value = scenario.startsWith('list_') ? {files: [{id: 'old', filename: 'Old private file', page_count: 1}]} :
        scenario === 'preview_after_lock' ? doc('old') : scenario === 'history_after_lock' ? {tasks} : {id: 'old-upload'};
    late.resolve(response(value)); await pending;
    assert.equal(JSON.stringify([...elements]), state); assert.equal(requests.length, before);
    assert.equal(downloadCount, 0); assert.deepEqual(voices, []);
})().catch(error => {console.error(error); process.exitCode = 1;});

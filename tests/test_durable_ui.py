"""Exercise the browser recovery functions with deterministic network responses."""
import json
import re
import subprocess
from pathlib import Path


def test_browser_keeps_multiple_handles_and_sends_owner_token():
    html = Path('ui/index.html').read_text()
    source = next(s for s in re.findall(r'<script>(.*?)</script>', html, re.S) if 'const API_URL' in s)
    script = '''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const storage = new Map();
const requests = [];
const context = {
 localStorage: {getItem: k => storage.get(k) || null, setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)},
 window: {crypto: require('node:crypto').webcrypto},
 document: {addEventListener() {}},
 setTimeout: fn => fn(),
 fetch: async (url, options) => {requests.push({url, options}); return {ok: true, json: async () => ({status: 'interrupted'})};},
};
vm.createContext(context);
vm.runInContext(SOURCE, context);
(async () => {
 vm.runInContext('rememberPendingRequest("one", "first"); rememberPendingRequest("two", "second"); clearPendingRequest("one");', context);
 const tasks = JSON.parse(storage.get('project-l-saved-tasks'));
 assert.equal(tasks.length, 2);
 assert.equal(tasks[0].pending, false);
 assert.equal(tasks[1].pending, true);
 assert.equal(JSON.parse(storage.get('project-l-pending-request')).requestId, 'two');
 const result = await vm.runInContext('recoverChatResponse("two")', context);
 assert.match(result.reply, /interrupted/);
 assert.equal(requests.length, 1);
 assert.equal(requests[0].options.headers['X-L-Recovery-Token'].length, 64);
 const first = requests[0].options.headers['X-L-Recovery-Token'];
 assert.equal(vm.runInContext('recoveryHeaders()["X-L-Recovery-Token"]', context), first);
})().catch(err => {console.error(err); process.exitCode = 1;});
'''.replace('SOURCE', json.dumps(source))
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)

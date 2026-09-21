"""Execute browser recovery with a virtual clock and stalled network/body reads."""
import json
from pathlib import Path
import re
import subprocess

import pytest


@pytest.mark.parametrize("scenario", [
    "stalled_fetch", "stalled_body", "pending", "transient_failure",
    "uncertain_submit", "no_double_wait", "recover_after_submit_timeout",
    "saved_button", "resume_pending", "late_response",
])
def test_layer89_recovery_is_bounded_without_replaying_tasks(scenario):
    source = next(s for s in re.findall(r"<script>(.*?)</script>",
                                       Path("ui/index.html").read_text(), re.S)
                  if "const API_URL" in s)
    script = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const storage = new Map(), elements = new Map(), timers = new Map();
const requests = [], shown = [], voices = [];
let now = 0, nextTimer = 0, aborted = 0, lateResolve;
const never = () => new Promise(() => {});
const ready = {status: 'ready', result: {reply: 'Recovered exact answer'}};
function element() {
 return {textContent: '', value: '', removed: false, children: [],
  remove() {this.removed = true;},
  appendChild(child) {this.children.push(child); shown.push(child);},
  insertBefore(child) {elements.set(child.id, child);}};
}
for (const id of ['chat', 'message', 'chatToolsActions', 'closeChatTools']) elements.set(id, element());
const context = {
 AbortController, TextEncoder,
 performance: {now: () => now},
 window: {crypto: require('node:crypto').webcrypto,
  lVoice: {canSend: () => true, saveDraft() {}, onReply: (...args) => voices.push(args)}},
 document: {addEventListener() {}, createElement: element, getElementById: id => elements.get(id)},
 localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
 setTimeout(fn, delay) {const id = ++nextTimer; timers.set(id, {fn, at: now + delay}); return id;},
 clearTimeout: id => timers.delete(id),
 fetch: async (url, options) => {
  requests.push({url, options});
  options.signal.addEventListener('abort', () => aborted++);
  if (options.method === 'POST') {
   if (['uncertain_submit', 'recover_after_submit_timeout'].includes(SCENARIO)) return never();
   return {ok: true, json: async () => ({status: 'queued'})};
  }
  if (SCENARIO === 'late_response') return new Promise(resolve => {lateResolve = resolve;});
  if (['stalled_fetch', 'saved_button', 'resume_pending'].includes(SCENARIO)) return never();
  if (SCENARIO === 'stalled_body') return {ok: true, json: never};
  if (SCENARIO === 'transient_failure' && requests.length === 1) return {ok: false, status: 503};
  return {ok: true, json: async () => ['pending', 'uncertain_submit', 'no_double_wait'].includes(SCENARIO)
    ? {status: 'running'} : ready};
 },
};
vm.createContext(context);
vm.runInContext(SOURCE, context);
async function drive(promise) {
 let done = false, value, failure;
 promise.then(v => {value = v; done = true;}, e => {failure = e; done = true;});
 for (let step = 0; step < 500 && !done; step++) {
  await new Promise(setImmediate);
  if (done) break;
  const entry = [...timers.entries()].sort((a,b) => a[1].at - b[1].at)[0];
  assert.ok(entry, 'operation stalled with no recovery timer');
  timers.delete(entry[0]); now = entry[1].at; entry[1].fn();
 }
 assert.ok(done, 'operation exceeded bounded test clock');
 if (failure) throw failure;
 return value;
}
const saved = () => JSON.parse(storage.get('project-l-saved-tasks') || '[]');
(async () => {
 if (['uncertain_submit', 'no_double_wait', 'recover_after_submit_timeout'].includes(SCENARIO)) {
  elements.get('message').value = 'Keep my original task';
  await drive(vm.runInContext('sendMessage()', context));
  assert.equal(requests.filter(r => r.options.method === 'POST').length, 1);
  const task = saved()[0];
  assert.equal(task.message, 'Keep my original task');
  assert.ok(requests.filter(r => r.options.method !== 'POST').every(r => r.url.endsWith(task.requestId)));
  assert.ok(now <= (SCENARIO === 'no_double_wait' ? 120000 : 135000));
  if (SCENARIO === 'recover_after_submit_timeout') {
   assert.equal(task.pending, false);
   assert.equal(voices.length, 1);
   assert.equal(voices[0][0], ready.result.reply);
  } else {
   assert.equal(task.pending, true);
   assert.ok(storage.has('project-l-pending-request'));
   assert.equal(voices.length, 0);
   assert.ok(shown.some(e => /Check Saved answers before resending/.test(e.textContent)));
  }
  assert.ok(shown.filter(e => e.id?.startsWith('thinking-')).every(e => e.removed));
 } else if (SCENARIO === 'saved_button' || SCENARIO === 'resume_pending') {
  if (SCENARIO === 'resume_pending') vm.runInContext('rememberPendingRequest("task", "original")', context);
  await drive(vm.runInContext('resumePendingRequest()', context));
  if (SCENARIO === 'saved_button') {
   vm.runInContext('rememberPendingRequest("task", "original")', context);
   const button = elements.get('savedAnswersAction');
   await drive(button.onclick());
   assert.equal(button.disabled, false);
   assert.ok(shown.some(e => /temporarily unavailable/.test(e.textContent)));
  }
  assert.equal(saved()[0].pending, true);
  assert.ok(now <= 120000);
 } else if (SCENARIO === 'late_response') {
  await drive(vm.runInContext('fetchChatJson("/chat/result/task", {}).catch(() => "timeout")', context));
  assert.equal(now, 15000);
  assert.equal(aborted, 1);
  lateResolve({ok: true, json: async () => ready});
  await new Promise(setImmediate);
  assert.equal(shown.length, 0);
  assert.equal(voices.length, 0);
 } else {
  const result = await drive(vm.runInContext('recoverChatResponse("task")', context));
  if (SCENARIO === 'transient_failure') {
   assert.equal(result.reply, ready.result.reply);
   assert.equal(requests.length, 2);
   assert.equal(aborted, 0);
  } else {
   assert.equal(result, null);
   assert.ok(now <= 120000);
   assert.ok(requests.length <= 60);
   if (SCENARIO !== 'pending') assert.ok(aborted > 0);
  }
 }
 assert.equal(timers.size, 0, 'deadline timers must be cleaned up');
 assert.ok(SCENARIO === 'late_response' || requests.every(r => r.options.headers['X-L-Recovery-Token']?.length === 64));
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    script = "const SCENARIO = " + json.dumps(scenario) + ";\n" + script.replace("SOURCE", json.dumps(source))
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr

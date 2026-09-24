"""Saved answer failures must not hide later answers or settle unverified tasks."""
import json
from pathlib import Path
import re
import subprocess

import pytest


@pytest.mark.parametrize("scenario", ["http", "body", "timeout", "integrity", "running", "budget"])
def test_saved_answers_isolate_failures_and_settle_only_verified_results(scenario):
    source = next(s for s in re.findall(r"<script>(.*?)</script>", Path("ui/index.html").read_text(), re.S)
                  if "const API_URL" in s)
    script = r'''
const assert = require('node:assert/strict'), vm = require('node:vm');
const storage = new Map(), elements = new Map(), shown = [], calls = [], timers = new Map();
let now = 0, sequence = 0;
function element() { return {setAttribute(){}, append(...els){els.forEach(e=>this.appendChild(e));}, textContent:'', appendChild(e) {shown.push(e);},
 insertBefore(e) {elements.set(e.id,e);}, remove() {}}; }
for (const id of ['chat','chatToolsActions','closeChatTools']) elements.set(id,element());
const context = {AbortController, TextEncoder, performance:{now:()=>now},
 window:{addEventListener(){}, crypto:require('node:crypto').webcrypto},
 MutationObserver: class {observe(){}},
 document:{documentElement:{dataset:{account:'ready'}}, addEventListener(){}, createElement:element, getElementById:id=>elements.get(id)},
 localStorage:{getItem:k=>storage.get(k)||null, setItem:(k,v)=>storage.set(k,v), removeItem:k=>storage.delete(k)},
 setTimeout(fn,ms){const id=++sequence;timers.set(id,{fn,at:now+ms});return id;},
 clearTimeout:id=>timers.delete(id),
 fetch:async (url,options)=>{
  assert.equal(options.method,undefined,'Saved answers must never resubmit a task');
  assert.equal(options.headers['X-L-Recovery-Token'].length,64);
  calls.push(url);
  if (SCENARIO==='budget' || (calls.length===1 && SCENARIO==='timeout')) return new Promise(()=>{});
  if (calls.length===1) {
   if (SCENARIO==='http') return {ok:false,status:503};
   if (SCENARIO==='body') return {ok:true,json:async()=>{throw Error('invalid JSON');}};
   if (SCENARIO==='integrity') return {ok:true,json:async()=>({status:'ready',result:{reply:'DO NOT SHOW',delivery_receipt:null}})};
   if (SCENARIO==='running') return {ok:true,json:async()=>({status:'running'})};
  }
  return {ok:true,json:async()=>({status:'ready',result:{reply:'Verified later answer'}})};
 }};
vm.createContext(context); vm.runInContext(SOURCE,context);
async function drive(promise) {
 let done=false,error; promise.then(()=>done=true,e=>{done=true;error=e;});
 for(let i=0;i<100&&!done;i++) {
  await new Promise(setImmediate); if(done)break;
  const entry=[...timers.entries()].sort((a,b)=>a[1].at-b[1].at)[0];
  assert.ok(entry,'missing timeout');timers.delete(entry[0]);now=entry[1].at;entry[1].fn();
 }
 assert.ok(done);if(error)throw error;
}
(async()=>{
 await vm.runInContext('resumePendingRequest()',context);
 const count=SCENARIO==='budget'?20:2;
 for(let i=0;i<count;i++) vm.runInContext(`rememberPendingRequest('task-${i}', 'Question ${i}')`,context);
 const button=elements.get('savedAnswersAction');
 await drive(button.onclick());
 const tasks=JSON.parse(storage.get('project-l-saved-tasks'));
 assert.equal(button.disabled,false);assert.equal(timers.size,0);
 assert.equal(tasks.at(-1).pending,true);
 assert.ok(!shown.some(e=>e.textContent==='DO NOT SHOW'));
 if(SCENARIO==='budget') {
  assert.equal(now,120000);assert.equal(calls.length,8);
  assert.ok(tasks.every(t=>t.pending));assert.ok(storage.has('project-l-pending-request'));
 } else {
  assert.equal(calls.length,2);assert.ok(calls[1].endsWith('task-0'));
  assert.equal(tasks[0].pending,false);assert.ok(storage.has('project-l-pending-request'));
  assert.ok(shown.some(e=>e.textContent==='Verified later answer'));
  const questions=shown.filter(e=>e.className==='msg user').map(e=>e.textContent);
  assert.deepEqual(questions,['Question 1','Question 0']);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    script = "const SCENARIO=" + json.dumps(scenario) + ";\n" + script.replace("SOURCE", json.dumps(source))
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr

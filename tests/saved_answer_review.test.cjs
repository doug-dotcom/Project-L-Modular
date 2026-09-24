const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('ui/index.html','utf8');
const source=html.slice(html.indexOf('        function installSavedAnswerReview'),html.indexOf('        async function resumePendingRequest'));
const scenario=process.argv[2],events={},calls=[],cleared=[];
let mutation,resolveFetch,resolveVerify,clock=0;
const el=()=>({children:[],textContent:'',disabled:false,attributes:{},
 append(...nodes){this.children.push(...nodes)},setAttribute(k,v){this.attributes[k]=v},remove(){this.removed=true},focus(){this.focused=true}});
const button=el(),chat=el(),plus=el(),root={dataset:{account:'ready'}};
let tasks=Array.from({length:25},(_,i)=>({requestId:'task-'+i,message:'Question '+i}));
const context={window:{addEventListener:(k,f)=>events[k]=f,lChatTools:{close(){}}},
 document:{documentElement:root,createElement:el,getElementById:()=>plus},
 MutationObserver:class{constructor(f){mutation=f}observe(){}},performance:{now:()=>clock},
 savedTasks:()=>tasks,ANSWER_RECOVERY_BUDGET_MS:120000,CHAT_REQUEST_TIMEOUT_MS:15000,
 recoveryHeaders:()=>({'X-L-Recovery-Token':'fixture'}),
 fetchChatJson:async(url,options)=>{calls.push({url,options});if(scenario==='stop_fetch'||scenario==='account'||scenario==='restart'||(scenario==='continue_late'&&calls.length<=2))return new Promise(r=>resolveFetch=r);
 if(scenario==='mixed'&&calls.length===1)throw Error('PRIVATE');return {status:'ready',result:{reply:'answer'}};},
 verifyDeliveryReply:async()=>scenario==='stop_verify'?new Promise(r=>resolveVerify=r):{valid:true},
 savedAnswerText:r=>r.result.reply,clearPendingRequest:id=>cleared.push(id),
 appendChatMessage:(parent,role,text)=>{const node=el();node.textContent=text;parent.append(node);return node},button,chat};
vm.createContext(context);vm.runInContext(source+'\ninstallSavedAnswerReview(button,chat);',context);
const panel=()=>chat.children.at(-1),progress=()=>panel().children[1].textContent,stop=()=>panel().children[2].onclick();
const ready={status:'ready',result:{reply:'answer'}};
(async()=>{
 if(['reuse_question','copy_answer','copy_rejected'].includes(scenario)) {
  tasks=[{requestId:'one',message:'Original question'}];
  const draft=el();draft.value='Existing draft';
  let scrolls=0;draft.scrollIntoView=options=>{assert.equal(options.block,'nearest');assert.equal(options.behavior,'instant');scrolls++};
  context.document.getElementById=id=>id==='message'?draft:plus;
  const writes=[];context.navigator={clipboard:{writeText:async text=>writes.push(text)}};
  context.savedAnswerText=()=> 'Saved answer — facts have since changed.\n\nOriginal answer';
  if(scenario==='copy_rejected')context.verifyDeliveryReply=async()=>({valid:false});
  await button.onclick();const entry=panel().children[4].children[0];
  const actions=entry.children[3].children,status=entry.children[4];const before=calls.length;
  if(scenario==='reuse_question') {
   actions[0].onclick();assert.equal(draft.value,'Existing draft');assert.match(status.textContent,/draft is kept/);assert.equal(scrolls,0);
   draft.value='';actions[0].onclick();assert.equal(draft.value,'Original question');assert.equal(draft.focused,true);assert.equal(scrolls,1);
   assert.match(status.textContent,/before pressing Send/);
   events['l-account-ready']();draft.value='';actions[0].onclick();assert.equal(draft.value,'');
  }else if(scenario==='copy_answer'){
   assert.equal(actions[1].textContent,'Copy answer');await actions[1].onclick();
   assert.deepEqual(writes,['Saved answer — facts have since changed.\n\nOriginal answer']);
   context.navigator.clipboard.writeText=async()=>{throw Error('PRIVATE')};await actions[1].onclick();
   assert.match(status.textContent,/Could not copy/);assert.ok(!status.textContent.includes('PRIVATE'));
   assert.equal(actions[1].disabled,false);
   events['l-account-ready']();await actions[1].onclick();assert.equal(writes.length,1);
  }else assert.equal(actions.length,1);
  assert.equal(calls.length,before);return;
 }
 if(['status_filters','status_batches'].includes(scenario)) {
  if(scenario==='status_filters') {
   tasks=['good','stale','queued','running','failed','bad','missing','unknown','offline'].map(requestId=>({requestId,message:'Question '+requestId}));
   context.fetchChatJson=async url=>{
    calls.push(url);const id=url.split('/').at(-1);
    if(id==='offline')throw Error('PRIVATE');
    if(['queued','running','missing','unknown'].includes(id))return {status:id==='missing'?'not_found':id};
    return {status:id==='failed'?'failed':'ready',result:{reply:id},freshness:{status:id==='stale'?'superseded':'current'}};
   };
   context.verifyDeliveryReply=async result=>({valid:result.reply!=='bad'});
  }
  await button.onclick();const controls=panel().children[3];
  const search=controls.children[0].children[0],filter=controls.children[1].children[0];
  const visible=()=>panel().children[4].children.filter(e=>!e.hidden);
  const counts=()=>controls.children[2].textContent;
  const before=calls.length;
  if(scenario==='status_filters') {
   assert.match(counts(),/2 answers available; 2 still working; 8 need attention/);
   filter.value='available';filter.onchange();assert.equal(visible().length,2);
   search.value='stale';search.oninput();assert.equal(visible().length,1);
   filter.value='attention';filter.onchange();assert.equal(visible().length,1);
   search.value='';search.oninput();filter.value='working';filter.onchange();assert.equal(visible().length,2);
   search.value='running';search.oninput();assert.equal(visible().length,1);
   assert.match(counts(),/Showing 1 of 9/);assert.match(counts(),/2 answers available; 2 still working; 8 need attention/);
   assert.equal(calls.length,before);
  } else {
   assert.match(counts(),/20 answers available; 0 still working; 0 need attention/);
   filter.value='working';filter.onchange();assert.equal(visible().length,0);
   await panel().children[5].onclick();assert.equal(visible().length,0);
   assert.match(counts(),/25 answers available; 0 still working; 0 need attention/);
   filter.value='available';filter.onchange();assert.equal(visible().length,25);
  }
  return;
 }
 if(scenario==='escape') {
  context.fetchChatJson=async()=>new Promise(r=>resolveFetch=r);
  const pending=button.onclick(),old=panel();
  let prevented=0,stopped=0;
  const key={key:'Escape',preventDefault(){prevented++},stopPropagation(){stopped++}};
  old.onkeydown({...key,key:'Enter'});old.onkeydown({...key,isComposing:true});
  old.onkeydown({...key,defaultPrevented:true});
  assert.equal(old.removed,undefined);assert.equal(prevented,0);
  old.onkeydown(key);assert.equal(old.removed,true);assert.equal(plus.focused,true);
  assert.equal(button.disabled,false);assert.equal(prevented,1);assert.equal(stopped,1);
  resolveFetch(ready);await pending;assert.equal(cleared.length,0);assert.equal(old.children[4].children.length,0);
  tasks=[];await button.onclick();old.onkeydown(key);
  assert.equal(panel().removed,undefined);assert.equal(prevented,1);
  return;
 }
 if(scenario==='navigation') {
  await button.onclick();
  const entries=()=>panel().children[4].children;
  const controls=()=>panel().children[3].children[3].children;
  assert.ok(entries().every(e=>e.open===false));
  const before=calls.length;controls()[0].onclick();
  assert.ok(entries().every(e=>e.open===true));assert.equal(calls.length,before);
  await panel().children[5].onclick();assert.ok(entries().every(e=>e.open===true));
  controls()[1].onclick();assert.ok(entries().every(e=>e.open===false));
  const search=panel().children[3].children[0].children[0];search.value='No match';search.oninput();
  assert.ok(entries().every(e=>e.hidden));controls()[2].onclick();assert.ok(entries().every(e=>!e.hidden));
  const settled=cleared.length;
  context.fetchChatJson=async()=>new Promise(r=>resolveFetch=r);
  const pending=button.onclick();const closed=panel();controls()[3].onclick();
  assert.equal(closed.removed,true);assert.equal(plus.focused,true);assert.equal(button.disabled,false);
  resolveFetch(ready);await pending;assert.equal(cleared.length,settled);
  assert.equal(closed.children[4].children.length,0);
  return;
 }
 if(['search','attention','rejected_search','batch_filter'].includes(scenario)) {
  if(scenario!=='batch_filter') {
   tasks=[{requestId:'good',message:'Holiday plan'},{requestId:'stale',message:'Travel plan'},
          {requestId:'running',message:'Unfinished'},{requestId:'bad',message:'Damaged'}];
   context.fetchChatJson=async(url,options)=>{
    calls.push({url,options});const id=url.split('/').at(-1);
    if(id==='running')return {status:'running'};
    return {status:'ready',freshness:{status:id==='stale'?'superseded':'current'},
      result:{reply:id==='bad'?'REJECTED_SECRET':id==='good'?'Budget approved':'Old flights'}};
   };
   context.verifyDeliveryReply=async result=>({valid:result.reply!=='REJECTED_SECRET'});
  }
  await button.onclick();
  const controls=panel().children[3],search=controls.children[0].children[0],filter=controls.children[1].children[0];
  const entries=()=>panel().children[4].children.filter(e=>!e.hidden);
  const before=calls.length;
  if(scenario==='batch_filter') {
   search.value='Question 0';search.oninput();assert.equal(entries().length,0);
   await panel().children[5].onclick();assert.equal(entries().length,1);assert.equal(calls.length,25);
  } else if(scenario==='search') {
   search.value='  BUDGET  ';search.oninput();assert.equal(entries().length,1);
   search.value='no match';search.oninput();assert.equal(entries().length,0);
   assert.match(controls.children[2].textContent,/Showing 0 of 4/);
   search.value='';search.oninput();assert.equal(entries().length,4);
  } else if(scenario==='attention') {
   filter.value='attention';filter.onchange();assert.equal(entries().length,3);
   search.value='travel';search.oninput();assert.equal(entries().length,1);
   search.value='';search.oninput();filter.value='all';filter.onchange();assert.equal(entries().length,4);
  } else {
   search.value='REJECTED_SECRET';search.oninput();assert.equal(entries().length,0);
   assert.ok(!JSON.stringify(panel().children[4]).includes('REJECTED_SECRET'));
  }
  if(scenario!=='batch_filter')assert.equal(calls.length,before);
  return;
 }
 if(['pagination','snapshot','cap','account_between','continue_late'].includes(scenario)) {
  if(scenario==='cap')tasks=Array.from({length:105},(_,i)=>({requestId:'task-'+i,message:'Question '+i}));
  const first=button.onclick();
  const older=()=>panel().children[5];
  if(scenario==='continue_late') {
   const oldResolve=resolveFetch;stop();const next=older().onclick();
   oldResolve(ready);await first;assert.equal(button.disabled,true);assert.equal(cleared.length,0);
   resolveFetch(ready);await next;
   assert.equal(calls.length,21);assert.equal(cleared.length,20);
   assert.equal(new Set(cleared).size,20);assert.equal(cleared[0],'task-24');
   return;
  }
  await first;assert.equal(calls.length,20);assert.equal(older().disabled,false);
  if(scenario==='account_between') {
   events['l-account-ready']();await older().onclick();assert.equal(calls.length,20);assert.equal(panel().removed,true);return;
  }
  if(scenario==='snapshot')tasks.unshift({requestId:'new-task',message:'New'});
  while(!older().disabled)await older().onclick();
  const expected=scenario==='cap'?100:25;
  assert.equal(calls.length,expected);assert.equal(new Set(calls.map(c=>c.url)).size,expected);
  assert.match(calls.at(-1).url,scenario==='cap'?/task-5$/:/task-0$/);
  assert.equal(panel().children[4].children.length,expected);
  assert.match(progress(),/Review finished/);
  await older().onclick();assert.equal(calls.length,expected);
  return;
 }
 if(scenario==='empty')tasks=[];
 if(scenario==='locked')root.dataset.account='locked';
 const promise=button.onclick();
 if(['stop_fetch','account','restart'].includes(scenario)){
  if(scenario==='account'){root.dataset.account='locked';mutation();}else stop();
  if(scenario==='restart'){
   const oldResolve=resolveFetch;const second=button.onclick();const secondPanel=panel();
   oldResolve(ready);await promise;assert.equal(button.disabled,true);assert.equal(panel(),secondPanel);
   stop();resolveFetch(ready);await second;
  }else {resolveFetch(ready);await promise;}
  assert.equal(cleared.length,0);assert.equal(calls.length,scenario==='restart'?2:1);
  if(scenario==='account')assert.equal(panel().removed,true);else assert.match(progress(),/Stopped/);
 }else if(scenario==='stop_verify'){
  await new Promise(setImmediate);stop();resolveVerify({valid:true});await promise;
  assert.equal(cleared.length,0);assert.equal(panel().children[4].children.length,0);
 }else {
  await promise;
  if(scenario==='locked'){assert.equal(chat.children.length,0);assert.equal(calls.length,0);return;}
  if(scenario==='empty'){assert.equal(calls.length,0);assert.match(progress(),/after you send/);}
  else {
   assert.equal(calls.length,20);assert.match(calls[0].url,/task-24$/);assert.match(calls[19].url,/task-5$/);
   assert.match(progress(),/20 of 25/);assert.match(progress(),/checked does not mean completed/);
   assert.equal(cleared.length,scenario==='mixed'?19:20);
   assert.ok(!JSON.stringify(panel()).includes('PRIVATE'));
   assert.ok(calls.every(c=>c.options.method===undefined));
  }
 }
 assert.equal(button.disabled,false);console.log(scenario+' passed');
})().catch(e=>{console.error(e);process.exitCode=1});

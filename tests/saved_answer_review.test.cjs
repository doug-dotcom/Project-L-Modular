const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('ui/index.html','utf8');
const source=html.slice(html.indexOf('        function installSavedAnswerReview'),html.indexOf('        async function resumePendingRequest'));
const scenario=process.argv[2],events={},calls=[],cleared=[];
let mutation,resolveFetch,resolveVerify,clock=0;
const el=()=>({children:[],textContent:'',disabled:false,attributes:{},
 append(...nodes){for(const node of nodes){const i=this.children.indexOf(node);if(i>=0)this.children.splice(i,1);this.children.push(node)}},appendChild(node){this.children.push(node)},insertBefore(node,before){const i=this.children.indexOf(node);if(i>=0)this.children.splice(i,1);const j=this.children.indexOf(before);if(j<0)this.children.push(node);else this.children.splice(j,0,node)},setAttribute(k,v){this.attributes[k]=v},remove(){this.removed=true},focus(){this.focused=true}});
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
  }else {assert.equal(actions.length,2);assert.equal(actions[1].textContent,'Copy question');}
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
 if(['refresh','refresh_pending'].includes(scenario)) {
  tasks=[{requestId:'one',message:'Question one'}];
  const controls=()=>panel().children[3],refresh=()=>controls().children[3].children[4];
  const search=()=>controls().children[0].children[0],filter=()=>controls().children[1].children[0];
  let reads=0;
  context.fetchChatJson=async()=>{reads++;return {status:'running'}};
  await button.onclick();search().value='Question';search().oninput();
  filter().value='working';filter().onchange();controls().children[3].children[0].onclick();
  if(scenario==='refresh') {
   const old=panel();context.fetchChatJson=async()=>{reads++;return ready};
   tasks.push({requestId:'two',message:'Question two'});
   await refresh().onclick();assert.equal(old.removed,true);assert.equal(reads,3);
   assert.equal(search().value,'Question');assert.equal(filter().value,'working');
   const entries=panel().children[4].children;assert.equal(entries.length,2);
   assert.ok(entries.every(e=>e.open&&e.hidden));
   assert.match(controls().children[2].textContent,/2 answers available; 0 still working/);
   filter().value='available';filter().onchange();assert.ok(entries.every(e=>!e.hidden));
   const before=reads;await old.children[3].children[3].children[4].onclick();assert.equal(reads,before);
  }else {
   context.fetchChatJson=async()=>{reads++;return new Promise(r=>resolveFetch=r)};
   const pending=refresh().onclick(),old=panel(),oldRefresh=refresh();
   assert.equal(oldRefresh.disabled,true);await oldRefresh.onclick();assert.equal(reads,2);
   const late=resolveFetch;stop();assert.equal(oldRefresh.disabled,false);
   context.fetchChatJson=async()=>{reads++;return ready};await oldRefresh.onclick();
   const current=panel(),before=cleared.length;late(ready);await pending;
   assert.equal(panel(),current);assert.equal(cleared.length,before);assert.equal(old.children[4].children.length,0);
   events['l-account-ready']();const count=reads;await refresh().onclick();assert.equal(reads,count);
  }
  return;
 }
 if(['refresh_open_questions','refresh_older_questions','refresh_expansion_reset'].includes(scenario)) {
  const entries=()=>panel().children[4].children;
  const navigation=()=>panel().children[3].children[3].children;
  const refresh=()=>navigation()[4].onclick();
  const find=id=>entries().find(e=>e.children[1].textContent==='Question '+id);
  await button.onclick();
  find(24).open=true;find(22).open=true;
  if(scenario==='refresh_open_questions') {
   const search=panel().children[3].children[0].children[0];search.value='Question 24';search.oninput();
   tasks.push({requestId:'new',message:'New question'});
   await refresh();
   assert.equal(find(24).open,true);assert.equal(find(22).open,true);
   assert.equal(find(22).hidden,true);assert.equal(find(23).open,false);
   assert.equal(entries()[0].open,false);assert.equal(calls.length,40);
  }else {
   await panel().children[5].onclick();find(0).open=true;
   await refresh();assert.equal(entries().length,20);
   if(scenario==='refresh_expansion_reset') {
    navigation()[0].onclick();find(24).open=false;
    await refresh();assert.equal(find(24).open,false);assert.equal(find(23).open,true);
    navigation()[1].onclick();
   }else {await refresh();assert.equal(find(24).open,true);}
   await panel().children[5].onclick();
   assert.equal(find(0).open,scenario==='refresh_older_questions');
   assert.equal(find(1).open,false);
  }
  // Closing and opening a new review must discard the previous expansion choices.
  navigation()[3].onclick();await button.onclick();
  assert.ok(entries().every(e=>!e.open));
  return;
 }
 if(['latest_reply','latest_reply_empty'].includes(scenario)) {
  context.lastAssistantText=scenario==='latest_reply'?'Latest live reply':'';
  const appendSource=html.slice(html.indexOf('        function appendChatMessage'),html.indexOf('        function rememberPendingRequest'));
  vm.runInContext(appendSource,context);
  const initial=context.lastAssistantText;
  tasks=['good','stale','bad','missing','offline'].map(requestId=>({requestId,message:requestId}));
  context.fetchChatJson=async url=>{
   const id=url.split('/').at(-1);
   if(id==='offline')throw Error('PRIVATE');
   return {status:id==='missing'?'not_found':'ready',result:{reply:id},freshness:{status:id==='stale'?'superseded':'current'}};
  };
  context.verifyDeliveryReply=async result=>({valid:result.reply!=='bad'});
  await button.onclick();assert.equal(context.lastAssistantText,initial);
  assert.equal(panel().children[4].children.length,5);
  await panel().children[3].children[3].children[4].onclick();assert.equal(context.lastAssistantText,initial);
  context.appendChatMessage(chat,'assistant','A new live reply');assert.equal(context.lastAssistantText,'A new live reply');
  context.appendChatMessage(chat,'assistant error','Failed request');assert.equal(context.lastAssistantText,'A new live reply');
  context.appendChatMessage(chat,'assistant',"L is thinking...");assert.equal(context.lastAssistantText,'A new live reply');
  return;
 }
 if(['check_times','check_times_refresh'].includes(scenario)) {
  let now='2026-09-24T09:00:00.000Z';
  context.Date=class extends Date {constructor(){super(now)}};
  if(scenario==='check_times_refresh')tasks=[{requestId:'one',message:'One'}];
  await button.onclick();
  const times=()=>panel().children[4].children.map(e=>e.children[5]);
  assert.ok(times().every(t=>t.dateTime===now&&t.textContent.includes('device time')));
  assert.match(times()[0].textContent,/^Checked:/);
  const first=times()[0];now='2026-09-24T09:05:00.000Z';
  if(scenario==='check_times') {
   await panel().children[5].onclick();assert.equal(times().length,25);
   assert.equal(times()[0],first);assert.equal(first.dateTime,'2026-09-24T09:00:00.000Z');
   assert.equal(times()[20].dateTime,now);
   const search=panel().children[3].children[0].children[0];search.value='No match';search.oninput();
   assert.equal(first.dateTime,'2026-09-24T09:00:00.000Z');
  }else {
   context.fetchChatJson=async()=>{throw Error('PRIVATE')};
   await panel().children[3].children[3].children[4].onclick();
   assert.equal(times()[0].dateTime,now);assert.match(times()[0].textContent,/^Check attempted:/);
   assert.equal(first.dateTime,'2026-09-24T09:00:00.000Z');
  }
  return;
 }
 if(['result_reasons','empty_answers'].includes(scenario)) {
  const expected=scenario==='result_reasons'?{
   good:'Saved answer',stale:'Facts changed',unchecked:'Freshness unchecked',bad:'Verification failed',
   running:'Still working',queued:'Still working',failed:'Task stopped',interrupted:'Task stopped',
   missing:'Answer unavailable',unknown:'Status unavailable',offline:'Check unavailable'
  }:{empty:'No answer text',whitespace:'No answer text',empty_stale:'No answer text'};
  tasks=Object.keys(expected).map(requestId=>({requestId,message:requestId}));
  context.fetchChatJson=async url=>{
   const id=url.split('/').at(-1);
   if(id==='offline')throw Error('PRIVATE');
   const statuses={running:'running',queued:'queued',failed:'failed',interrupted:'interrupted',missing:'not_found',unknown:'unexpected'};
   return {status:statuses[id]||'ready',result:{reply:id.startsWith('empty')?'':id==='whitespace'?'   ':id},
    freshness:{status:id==='stale'||id==='empty_stale'?'superseded':id==='unchecked'?'unavailable':'current'}};
  };
  context.verifyDeliveryReply=async result=>({valid:result.reply!=='bad'});
  context.savedAnswerText=r=>r.freshness.status==='superseded'?'Freshness warning: '+r.result.reply:r.result.reply;
  await button.onclick();const entries=panel().children[4].children;
  for(const entry of entries){const id=entry.children[1].textContent;assert.equal(entry.children[0].textContent,expected[id]+' — '+id);}
  if(scenario==='empty_answers'){
   assert.ok(entries.every(e=>!e.children[3].children.some(c=>c.textContent==='Copy answer')));
   assert.match(panel().children[3].children[2].textContent,/0 answers available; 0 still working; 3 need attention/);
  }
  return;
 }
 if(['review_order','review_order_batches'].includes(scenario)) {
  if(scenario==='review_order')tasks=['old-bad','middle-good','new-bad','newest-good'].map(requestId=>({requestId,message:requestId}));
  let reads=0;context.fetchChatJson=async url=>{
   reads++;const id=url.split('/').at(-1);
   return id.includes('bad')||id==='task-0'?{status:'running'}:ready;
  };
  await button.onclick();const order=()=>panel().children[3].children[4].children[0];
  const ids=()=>panel().children[4].children.map(e=>e.children[1].textContent);
  const before=reads;order().value='attention';order().onchange();assert.equal(reads,before);
  if(scenario==='review_order') {
   assert.deepEqual(ids(),['new-bad','old-bad','newest-good','middle-good']);
   const search=panel().children[3].children[0].children[0];search.value='good';search.oninput();
   assert.deepEqual(panel().children[4].children.filter(e=>!e.hidden).map(e=>e.children[1].textContent),['newest-good','middle-good']);
   order().value='newest';order().onchange();assert.deepEqual(ids(),['newest-good','new-bad','middle-good','old-bad']);
   search.value='';search.oninput();order().value='attention';order().onchange();
   await panel().children[3].children[3].children[4].onclick();
   assert.equal(order().value,'attention');assert.deepEqual(ids(),['new-bad','old-bad','newest-good','middle-good']);
  } else {
   await panel().children[5].onclick();assert.equal(ids().length,25);assert.equal(new Set(ids()).size,25);
   assert.equal(ids()[0],'Question 0');assert.equal(ids()[1],'Question 24');
   order().value='newest';order().onchange();assert.equal(ids()[0],'Question 24');assert.equal(ids().at(-1),'Question 0');
  }
  return;
 }
 if(['status_search','empty_search_guidance'].includes(scenario)) {
  let reads=0;context.fetchChatJson=async url=>{
   reads++;const id=url.split('/').at(-1);
   if(id==='task-24')return {status:'running'};
   return {status:'ready',result:{reply:'Answer'},freshness:{status:id==='task-23'?'superseded':'current'}};
  };
  await button.onclick();const controls=panel().children[3],search=controls.children[0].children[0];
  const visible=()=>panel().children[4].children.filter(e=>!e.hidden);
  const before=reads;
  if(scenario==='status_search') {
   search.value='  STILL WORKING  ';search.oninput();assert.equal(visible().length,1);assert.equal(visible()[0].children[1].textContent,'Question 24');
   search.value='facts changed';search.oninput();assert.equal(visible().length,1);assert.equal(visible()[0].children[1].textContent,'Question 23');
   const filter=controls.children[1].children[0];filter.value='working';filter.onchange();assert.equal(visible().length,0);
   assert.match(controls.children[2].textContent,/No checked tasks match/);assert.equal(reads,before);
  }else {
   search.value='no such answer';search.oninput();
   assert.match(controls.children[2].textContent,/Use Clear filters/);assert.match(controls.children[2].textContent,/More tasks remain/);
   await panel().children[5].onclick();assert.ok(!controls.children[2].textContent.includes('More tasks remain'));
   assert.match(controls.children[2].textContent,/No checked tasks match/);
   controls.children[3].children[2].onclick();assert.equal(visible().length,25);
   assert.ok(!controls.children[2].textContent.includes('No checked tasks match'));assert.equal(reads,25);
  }
  return;
 }
 if(['copy_question','copy_question_blocked','copy_question_empty'].includes(scenario)) {
  tasks=[{requestId:'one',message:scenario==='copy_question_empty'?'   ':'Original question\nwith exact spacing  👊'}];
  const writes=[],draft={value:'Unsent draft'};let resolveCopy;
  context.document.getElementById=id=>id==='message'?draft:plus;
  context.navigator={clipboard:{writeText:async text=>{writes.push(text);if(scenario==='copy_question_blocked')return new Promise(r=>resolveCopy=r)}}};
  context.verifyDeliveryReply=async()=>({valid:false});
  await button.onclick();const entry=panel().children[4].children[0];
  const copy=entry.children[3].children.find(c=>c.textContent==='Copy question'),status=entry.children[4];
  const before=calls.length;
  if(scenario==='copy_question_empty'){assert.equal(copy,undefined);return;}
  const pending=copy.onclick();
  if(scenario==='copy_question_blocked') {
   assert.equal(copy.disabled,true);await copy.onclick();assert.equal(writes.length,1);
   events['l-account-ready']();resolveCopy();await pending;assert.equal(status.textContent,'');
   await copy.onclick();assert.equal(writes.length,1);
  }else {
   await pending;assert.deepEqual(writes,[tasks[0].message]);assert.match(status.textContent,/Original question copied/);
   context.navigator.clipboard.writeText=async()=>{throw Error('PRIVATE')};await copy.onclick();
   assert.match(status.textContent,/Select the question text/);assert.ok(!status.textContent.includes('PRIVATE'));assert.equal(copy.disabled,false);
  }
  assert.equal(draft.value,'Unsent draft');assert.equal(calls.length,before);
  return;
 }
 if(['copy_exchange','copy_exchange_gates','copy_exchange_stale'].includes(scenario)) {
  tasks=[{requestId:'one',message:'Original question\nExact spacing  👊'}];
  const writes=[],draft={value:'Unsent draft'};let resolveCopy;
  context.document.getElementById=id=>id==='message'?draft:plus;
  // Exercise the production freshness formatter, including its warning prefix.
  const formatter=html.slice(html.indexOf('        function savedAnswerText'),html.indexOf('        function savedAnswerText')+3000);
  vm.runInContext(formatter.slice(0,formatter.indexOf('\n        }')+10),context);
  context.fetchChatJson=async()=>({status:'ready',result:{reply:'Saved answer\nExact spacing  '},freshness:{status:'superseded'}});
  context.navigator={clipboard:{writeText:async text=>{writes.push(text);if(scenario==='copy_exchange_stale')return new Promise(r=>resolveCopy=r)}}};
  const getCopy=()=>panel().children[4].children[0].children[3].children.find(c=>c.textContent==='Copy question and answer');
  if(scenario==='copy_exchange_gates') {
   for(const result of [{status:'running'},{status:'failed',result:{reply:'Partial'}},{status:'ready',result:{reply:'  '}}]) {
    context.fetchChatJson=async()=>result;await button.onclick();assert.equal(getCopy(),undefined);
   }
   context.fetchChatJson=async()=>ready;context.verifyDeliveryReply=async()=>({valid:false});
   await button.onclick();assert.equal(getCopy(),undefined);
   context.verifyDeliveryReply=async()=>({valid:true});tasks[0].message='   ';
   await button.onclick();assert.equal(getCopy(),undefined);assert.equal(writes.length,0);return;
  }
  await button.onclick();const copy=getCopy(),entry=panel().children[4].children[0],status=entry.children[4];
  const expected='Question:\n'+tasks[0].message+'\n\nAnswer:\n'+entry.children[2].textContent;
  assert.match(expected,/changed|superseded/i);
  const before=calls.length,pending=copy.onclick();
  if(scenario==='copy_exchange_stale') {
   await copy.onclick();assert.equal(writes.length,1);
   panel().children[3].children[3].children[3].onclick();resolveCopy();await pending;
   assert.equal(status.textContent,'');await copy.onclick();assert.equal(writes.length,1);
  }else {
   await pending;assert.deepEqual(writes,[expected]);assert.match(status.textContent,/Question and saved answer copied/);
   context.navigator.clipboard.writeText=async()=>{throw Error('PRIVATE')};await copy.onclick();
   assert.match(status.textContent,/Select the question and answer text/);assert.ok(!status.textContent.includes('PRIVATE'));
  }
  assert.equal(draft.value,'Unsent draft');assert.equal(copy.disabled,false);assert.equal(calls.length,before);return;
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

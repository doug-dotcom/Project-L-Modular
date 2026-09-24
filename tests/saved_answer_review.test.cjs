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
 fetchChatJson:async(url,options)=>{calls.push({url,options});if(scenario==='stop_fetch'||scenario==='account'||scenario==='restart')return new Promise(r=>resolveFetch=r);
 if(scenario==='mixed'&&calls.length===1)throw Error('PRIVATE');return {status:'ready',result:{reply:'answer'}};},
 verifyDeliveryReply:async()=>scenario==='stop_verify'?new Promise(r=>resolveVerify=r):{valid:true},
 savedAnswerText:r=>r.result.reply,clearPendingRequest:id=>cleared.push(id),
 appendChatMessage:(parent,role,text)=>{const node=el();node.textContent=text;parent.append(node);return node},button,chat};
vm.createContext(context);vm.runInContext(source+'\ninstallSavedAnswerReview(button,chat);',context);
const panel=()=>chat.children.at(-1),progress=()=>panel().children[1].textContent,stop=()=>panel().children[2].onclick();
const ready={status:'ready',result:{reply:'answer'}};
(async()=>{
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
  assert.equal(cleared.length,0);assert.equal(panel().children[3].children.length,0);
 }else {
  await promise;
  if(scenario==='locked'){assert.equal(chat.children.length,0);assert.equal(calls.length,0);return;}
  if(scenario==='empty'){assert.equal(calls.length,0);assert.match(progress(),/after you send/);}
  else {
   assert.equal(calls.length,20);assert.match(calls[0].url,/task-24$/);assert.match(calls[19].url,/task-5$/);
   assert.match(progress(),/20 of 20/);assert.match(progress(),/checked does not mean completed/);
   assert.equal(cleared.length,scenario==='mixed'?19:20);
   assert.ok(!JSON.stringify(panel()).includes('PRIVATE'));
   assert.ok(calls.every(c=>c.options.method===undefined));
  }
 }
 assert.equal(button.disabled,false);console.log(scenario+' passed');
})().catch(e=>{console.error(e);process.exitCode=1});

const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('ui/index.html','utf8');
const source=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('const API_URL'));
const scenario=process.argv[2],storage=new Map(),requests=[],messages=[],drafts=[];
const original='  Keep my exact draft\nwith spacing  👊  ';
const input={value:original,focus(){this.focused=true}},chat={scrollHeight:10};
const failureKey={token:'project-l-recovery-token',tasks:'project-l-saved-tasks',pending:'project-l-pending-request'}[scenario];
let blocked=true;
if(scenario==='malformed')storage.set('project-l-saved-tasks','null');
const context={window:{crypto:require('node:crypto').webcrypto,lVoice:{canSend:()=>true,saveDraft:()=>drafts.push(input.value),onReply(){}}},
 document:{addEventListener(){},getElementById:id=>id==='message'?input:chat},
 localStorage:{getItem:k=>storage.get(k)||null,setItem(k,v){if(blocked&&k===failureKey)throw Error('PRIVATE storage error');storage.set(k,v)},removeItem:k=>storage.delete(k)}};
vm.createContext(context);vm.runInContext(source,context);
context.appendChatMessage=(parent,role,text)=>{const m={role,text,remove(){this.removed=true}};messages.push(m);return m};
context.fetchChatJson=async(url,options)=>{requests.push({url,options});return {status:'queued'}};
context.recoverChatResponse=async()=>({reply:'Answer'});
(async()=>{
 await context.sendMessage();
 assert.equal(input.value,original);assert.equal(input.focused,true);assert.equal(requests.length,0);
 assert.equal(drafts.length,0);assert.equal(messages.length,1);assert.equal(messages[0].role,'assistant error');
 assert.match(messages[0].text,/has not been sent/);assert.match(messages[0].text,/draft is still/);
 assert.ok(!messages[0].text.includes('PRIVATE'));
 blocked=false;if(scenario==='malformed')storage.set('project-l-saved-tasks','[]');
 await context.sendMessage();
 assert.equal(input.value,'');assert.deepEqual(drafts,['']);assert.equal(requests.length,1);
 assert.equal(JSON.parse(requests[0].options.body).message,original.trim());
 assert.equal(requests[0].options.headers['X-L-Recovery-Token'],storage.get('project-l-recovery-token'));
 assert.equal(messages.filter(m=>m.role==='user').length,1);assert.equal(messages.at(-1).text,'Answer');
})().catch(err=>{console.error(err);process.exitCode=1});

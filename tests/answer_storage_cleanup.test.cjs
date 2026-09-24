const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('ui/index.html','utf8');
const source=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('const API_URL'));
const scenario=process.argv[2],storage=new Map(),requests=[],messages=[],spoken=[];
let fail=false,recoveries=0;
const input={value:'My question'},chat={scrollHeight:10};
const context={window:{crypto:require('node:crypto').webcrypto,lVoice:{canSend:()=>true,saveDraft(){},onReply:text=>spoken.push(text)}},
 document:{addEventListener(){},getElementById:id=>id==='message'?input:chat},
 localStorage:{getItem:k=>storage.get(k)||null,
 setItem(k,v){if(fail&&scenario!=='remove')throw Error('PRIVATE');storage.set(k,v)},
 removeItem(k){if(fail&&scenario==='remove')throw Error('PRIVATE');storage.delete(k)}}};
vm.createContext(context);vm.runInContext(source,context);
context.appendChatMessage=(parent,role,text)=>{const m={role,text,remove(){this.removed=true}};messages.push(m);return m};
context.fetchChatJson=async(url,options)=>{requests.push({url,options});if(scenario==='uncertain')throw Error('Connection lost');return {status:'queued'}};
context.recoverChatResponse=async()=>{recoveries++;fail=true;return {reply:'Delivered answer'}};
(async()=>{
 await context.sendMessage();
 assert.equal(requests.length,1);assert.equal(recoveries,1);
 assert.equal(messages.at(-1).text,'Delivered answer');assert.deepEqual(spoken,['Delivered answer']);
 assert.equal(messages.filter(m=>m.role==='assistant error').length,0);
 const id=JSON.parse(requests[0].options.body).request_id;
 assert.ok(JSON.parse(storage.get('project-l-saved-tasks')).some(t=>t.requestId===id));
 assert.equal(context.clearPendingRequest(id),false);
 fail=false;assert.equal(context.clearPendingRequest(id),true);
 assert.equal(JSON.parse(storage.get('project-l-saved-tasks'))[0].pending,false);
 assert.equal(storage.has('project-l-pending-request'),false);
 assert.equal(requests.length,1);
})().catch(err=>{console.error(err);process.exitCode=1});

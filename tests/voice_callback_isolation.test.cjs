const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('ui/index.html','utf8');
const source=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('const API_URL'));
const scenario=process.argv[2],storage=new Map(),requests=[],messages=[],voiceCalls=[];
let recoveries=0;
const input={value:'Typed question'},chat={scrollHeight:10};
const context={window:{crypto:require('node:crypto').webcrypto,lVoice:{canSend:()=>true,
 saveDraft(){voiceCalls.push('draft');if(['draft','both'].includes(scenario))throw Error('PRIVATE draft failure')},
 onReply(){voiceCalls.push('reply');if(scenario!=='draft')throw Error('PRIVATE voice failure')}}},
 document:{addEventListener(){},getElementById:id=>id==='message'?input:chat},
 localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}};
vm.createContext(context);vm.runInContext(source,context);
context.appendChatMessage=(parent,role,text)=>{const m={role,text,removed:false,remove(){this.removed=true}};messages.push(m);return m};
context.fetchChatJson=async(url,options)=>{requests.push({url,options});if(scenario==='uncertain')throw Error('Connection lost');return {status:'queued'}};
context.recoverChatResponse=async()=>{recoveries++;return {reply:'Delivered answer'}};
(async()=>{
 await context.sendMessage();
 assert.equal(requests.length,1);assert.equal(recoveries,1);assert.equal(input.value,'');
 assert.equal(messages.filter(m=>m.role==='assistant'&&!m.removed).length,1);
 assert.equal(messages.at(-1).text,'Delivered answer');assert.equal(messages.filter(m=>m.role==='assistant error').length,0);
 assert.deepEqual(voiceCalls,['draft','reply']);
 assert.equal(JSON.parse(storage.get('project-l-saved-tasks'))[0].pending,false);
 assert.equal(storage.has('project-l-pending-request'),false);
 assert.ok(!JSON.stringify(messages).includes('PRIVATE'));
})().catch(err=>{console.error(err);process.exitCode=1});

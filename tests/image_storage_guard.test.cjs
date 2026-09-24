const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('ui/index.html','utf8'),scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const scenario=process.argv[2],storage=new Map(),requests=[],messages=[],previews=[];
let blocked=true;const file={name:'picture.jpg'},original='  My picture prompt\nExact spacing  👊  ';
const input={value:original,focus(){this.focused=true}},fileInput={value:'selected-picture',files:[file]},chat={scrollHeight:10,appendChild:n=>previews.push(n)};
const key=scenario==='pending'?'project-l-pending-request':'project-l-saved-tasks';
if(scenario==='malformed')storage.set(key,'null');
const context={window:{crypto:require('node:crypto').webcrypto},
 document:{addEventListener(){},createElement:()=>({style:{}}),getElementById:id=>id==='message'?input:id==='fileInput'?fileInput:chat},
 URL:{createObjectURL:()=> 'blob:fixture'},FormData:class{constructor(){this.fields={}}append(k,v){this.fields[k]=v}},
 localStorage:{getItem:k=>storage.get(k)||null,setItem(k,v){if(blocked&&scenario!=='malformed'&&k===key)throw Error('PRIVATE');storage.set(k,v)},removeItem:k=>storage.delete(k)},
 fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>({status:'queued'})}}};
vm.createContext(context);vm.runInContext(scripts.find(s=>s.includes('const API_URL')),context);
vm.runInContext(scripts.find(s=>s.includes('async function submitImage')),context);
context.appendChatMessage=(parent,role,text)=>{const m={role,text,remove(){}};messages.push(m);return m};
context.recoverChatResponse=async()=>({reply:'Picture answer'});
(async()=>{
 await context.submitImage(file);
 assert.equal(input.value,original);assert.equal(fileInput.value,'selected-picture');assert.equal(fileInput.files[0],file);
 assert.equal(input.focused,true);assert.equal(previews.length,0);assert.equal(requests.length,0);
 assert.equal(messages.length,1);assert.match(messages[0].text,/has not been uploaded/);assert.ok(!messages[0].text.includes('PRIVATE'));
 blocked=false;if(scenario==='malformed')storage.set(key,'[]');
 await context.submitImage(file);
 assert.equal(requests.length,1);assert.equal(previews.length,1);assert.equal(input.value,'');assert.equal(fileInput.value,'');
 assert.equal(requests[0].options.body.fields.file,file);assert.equal(requests[0].options.body.fields.prompt,original.trim());
 assert.equal(messages.at(-1).text,'Picture answer');assert.equal(messages.filter(m=>m.role==='user').length,1);
})().catch(err=>{console.error(err);process.exitCode=1});

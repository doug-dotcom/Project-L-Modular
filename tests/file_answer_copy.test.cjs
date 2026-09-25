const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scenario=process.argv[2],elements=new Map(),storage=new Map(),writes=[],voices=[];let initialise,mutation,reply='Answer text';
const root={dataset:{account:'ready'}},deferred=()=>{let resolve,reject;const promise=new Promise((y,n)=>{resolve=y;reject=n;});return{promise,resolve,reject};};
const element=()=>({value:'',textContent:'',disabled:false,children:[],replaceChildren(...n){this.children=n;},add(n){this.children.push(n);}});
const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
const source={filename:'notes.pdf',page:2,quotes:['Exact source quote'],kind:scenario==='image'?'image':'text'};
const pending=deferred();let handler=async()=>{};
if(['double','page','locked','newanswer'].includes(scenario))handler=()=>pending.promise;
if(scenario==='failure')handler=async()=>{throw Error('PRIVATE clipboard failure');};
const context={AbortController,setTimeout,clearTimeout,performance:{now:()=>0},crypto:require('node:crypto').webcrypto,
 document:{documentElement:root,addEventListener(_,fn){initialise=fn;},getElementById:el},
 window:{addEventListener(){},lVoice:{onReply:reply=>voices.push(reply)}},MutationObserver:class{constructor(fn){mutation=fn;}observe(){}},
 Option:class{constructor(text,value){this.text=text;this.value=value;}},
 navigator:scenario==='unavailable'?{}:{clipboard:{writeText(text){writes.push(text);return handler();}}},
 sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 fetch:async url=>({ok:true,json:async()=>url==='/evidence/files'?{files:[{id:'doc',filename:'notes.pdf',page_count:2}]}:{id:'doc',page_count:2,pages:[{text:'One'},{text:'Two'}]}}),
 fetchChatJson:async url=>url==='/evidence/ask'?{status:'queued'}:{status:'ready',result:scenario==='malformed'?null:{reply,...(scenario==='plain'?{}:{evidence:source})}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
const ask=()=>{el('evidenceQuestion').value='Question '+reply;return el('askEvidence').onclick();};
(async()=>{
 assert.equal(el('copyEvidence').disabled,true);await el('copyEvidence').onclick();assert.equal(writes.length,0);
 el('evidenceFiles').value='doc';await el('evidenceFiles').onchange();await ask();
 if(scenario==='malformed'){assert.equal(el('copyEvidence').disabled,true);await el('copyEvidence').onclick();assert.equal(writes.length,0);return;}
 assert.equal(el('copyEvidence').disabled,false);
 const text=el('evidenceAnswer').textContent,status=el('evidenceStatus').textContent,voiceCount=voices.length;
 if(scenario==='refresh')await el('refreshFiles').onclick();
 const copy=el('copyEvidence').onclick();
 if(['double','page','locked','newanswer'].includes(scenario)){
  assert.equal(el('copyEvidence').disabled,true);await el('copyEvidence').onclick();assert.equal(writes.length,1);
  if(scenario==='page'){el('evidencePage').value=2;el('evidencePage').onchange();}
  if(scenario==='locked'){root.dataset.account='locked';mutation();}
  if(scenario==='newanswer'){reply='New answer';await ask();assert.equal(el('copyEvidence').disabled,true);}
  pending.resolve();
 }
 await copy;
 if(['page','locked','newanswer'].includes(scenario)){
  assert.equal(el('evidenceCopyStatus').textContent,'');assert.equal(el('copyEvidence').disabled,scenario!=='newanswer');
  assert.equal(writes[0],text);return;
 }
 assert.equal(el('evidenceAnswer').textContent,text);assert.equal(el('evidenceStatus').textContent,status);assert.equal(voices.length,voiceCount);
 assert.equal(el('copyEvidence').disabled,false);
 if(['failure','unavailable'].includes(scenario)){
  assert.match(el('evidenceCopyStatus').textContent,/Could not copy.*manually/);assert.ok(!el('evidenceCopyStatus').textContent.includes('PRIVATE'));
 }else{
  assert.deepEqual(writes,[text]);assert.match(el('evidenceCopyStatus').textContent,/copied/);
  if(scenario!=='plain'){assert.match(writes[0],/Source: notes.pdf, physical page 2/);assert.match(writes[0],/Exact source quote/);}
  if(scenario==='image')assert.match(writes[0],/Image interpretation by the model/);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});

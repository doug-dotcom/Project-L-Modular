const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scenario=process.argv[2],elements=new Map(),requests=[],voices=[],root={dataset:{account:'ready'}};
let initialise,mutation;
const deferred=()=>{let resolve,reject;const promise=new Promise((y,n)=>{resolve=y;reject=n;});return{promise,resolve,reject};};
const element=()=>({value:'',textContent:'',disabled:false,children:[],replaceChildren(...n){this.children=n;},appendChild(n){this.children.push(n);},add(n){this.children.push(n);}});
const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
const doc=(id,pages=2)=>({id,filename:id+'.pdf',page_count:pages,pages:Array.from({length:pages},(_,i)=>({text:id+' page '+(i+1)}))});
const summary=(id,pages=2)=>({id,filename:id+'.pdf',page_count:pages});
const task=scenario==='legacy'
 ? {request_id:'legacy',status:'ready',request:{question:'Legacy question'}}
 : {request_id:'saved',status:'ready',request:{document_id:'target',page:2,question:'Saved question'}};
const response=value=>({ok:true,json:async()=>value});
const late=deferred();
let handler=async url=>{
 if(url==='/evidence/files') {
  if(scenario==='malformed') return response({files:[{}]});
  if(scenario==='missing') return response({files:[summary('current')]});
  return response({files:[summary('current'),summary('target',scenario==='pagegone'?1:2)]});
 }
 if(url==='/evidence/files/current') return response(doc('current'));
 if(url==='/evidence/files/target') {
  if(['pagechange','account'].includes(scenario)) return late.promise;
  return response(doc('target',scenario==='pagegone'?1:2));
 }
 if(url==='/evidence/tasks') return response({tasks:[task]});
 throw Error('Unexpected fetch '+url);
};
const context={AbortController,setTimeout,clearTimeout,performance:{now:()=>0},
 document:{documentElement:root,addEventListener(_,fn){initialise=fn;},getElementById:el,createElement:element},
 window:{addEventListener(){},lVoice:{onReply:text=>voices.push(text)}},
 MutationObserver:class{constructor(fn){mutation=fn;}observe(){}},
 Option:class{constructor(text,value){this.text=text;this.value=value;}},
 sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},
 fetch:(url,options={})=>{requests.push({url,options});return handler(url,options);},
 fetchChatJson:async(url,options={})=>{requests.push({url,options});return{status:'ready',result:{reply:'Recovered answer',evidence:{filename:'target.pdf',page:2,quotes:['Saved quote']}}};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
(async()=>{
 el('evidenceFiles').value='current';await el('evidenceFiles').onchange();
 el('evidenceQuestion').value='Current draft';el('evidenceAnswer').textContent='Current answer';
 await el('evidenceHistory').onclick();
 const button=el('evidenceTasks').children[0];assert.ok(button);
 const pending=button.onclick();await flush();
 if(scenario==='pagechange'){
  el('evidencePage').value=2;el('evidencePage').onchange();
  late.resolve(response(doc('target')));await pending;
  assert.equal(el('evidenceFiles').value,'current');assert.equal(el('evidencePage').value,2);
  assert.equal(el('evidencePreview').textContent,'current page 2');
  assert.ok(!requests.some(r=>r.url==='/evidence/tasks/saved'));return;
 }
 if(scenario==='account'){
  root.dataset.account='locked';mutation();late.resolve(response(doc('target')));await pending;
  assert.equal(el('evidenceFiles').value,'');assert.equal(el('evidencePreview').textContent,'');
  assert.ok(!requests.some(r=>r.url==='/evidence/tasks/saved'));return;
 }
 await pending;
 if(['missing','pagegone','malformed'].includes(scenario)){
  assert.equal(el('evidenceFiles').value,'current');assert.equal(el('evidenceQuestion').value,'Current draft');
  assert.equal(el('evidencePreview').textContent,'current page 1');assert.equal(el('evidenceAnswer').textContent,'Current answer');
  assert.match(el('evidenceStatus').textContent,/original file or page could not be confirmed/);
  assert.ok(!requests.some(r=>r.url==='/evidence/tasks/saved'));return;
 }
 if(scenario==='legacy'){
  assert.equal(el('evidenceFiles').value,'');assert.equal(el('evidencePreview').textContent,'');
  assert.equal(el('evidenceQuestion').value,'Legacy question');
  assert.equal(el('evidenceAnswer').textContent,'Recovered answer');
  assert.ok(requests.some(r=>r.url==='/evidence/tasks/legacy'));
  assert.ok(!requests.some(r=>r.url==='/evidence/ask'));return;
 }
 assert.equal(el('evidenceFiles').value,'target');assert.equal(el('evidencePage').value,2);
 assert.equal(el('evidencePreview').textContent,'target page 2');assert.equal(el('evidenceQuestion').value,'Saved question');
 assert.match(el('evidenceAnswer').textContent,/Recovered answer/);assert.match(el('evidenceAnswer').textContent,/target\.pdf/);
 assert.ok(requests.some(r=>r.url==='/evidence/tasks/saved'));
 assert.ok(!requests.some(r=>r.url==='/evidence/ask'));assert.deepEqual(voices,['Recovered answer']);
})().catch(e=>{console.error(e);process.exitCode=1;});

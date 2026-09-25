const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scenario=process.argv[2],elements=new Map(),requests=[],storage=new Map();let initialise,handler,answerHandler;
const element=()=>({value:'',textContent:'',disabled:false,children:[],replaceChildren(...n){this.children=n;},appendChild(n){this.children.push(n);},add(n){this.children.push(n);}});
const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
const doc=id=>({id,filename:id+'.pdf',page_count:2,pages:[{text:id+' page one'},{text:id+' page two'}]});
const response=value=>({ok:true,json:async()=>value});
const deferred=()=>{let resolve,reject;const promise=new Promise((y,n)=>{resolve=y;reject=n;});return{promise,resolve,reject};};
handler=async url=>response(url==='/evidence/files'?{files:[doc('doc')]}:doc(url.split('/').at(-1)));
answerHandler=async url=>url==='/evidence/ask'?{status:'queued'}:{status:'ready',result:{reply:'Recovered answer'}};
const context={AbortController,setTimeout,clearTimeout,performance:{now:()=>0},crypto:require('node:crypto').webcrypto,
 document:{documentElement:{dataset:{account:'ready'}},addEventListener(_,fn){initialise=fn;},getElementById:el,createElement:element},
 window:{addEventListener(){}},MutationObserver:class{observe(){}},Option:class{constructor(text,value){this.text=text;this.value=value;}},FormData:class{append(){}},
 sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 fetch:(url,options={})=>{requests.push({url,options});return handler(url,options);},
 fetchChatJson:(url,options={})=>{requests.push({url,options});return answerHandler(url,options);}};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
const refresh=()=>el('refreshFiles').onclick(),flush=()=>new Promise(setImmediate);
(async()=>{
 el('evidenceFiles').value='doc';await el('evidenceFiles').onchange();
 el('evidencePage').value=2;el('evidencePage').onchange();el('evidenceQuestion').value='Draft question';el('evidenceAnswer').textContent='Previous answer';
 const reads=()=>requests.filter(r=>r.url==='/evidence/files/doc').length;
 if(scenario==='pending'){
  const wait=deferred();answerHandler=url=>url==='/evidence/ask'?Promise.resolve({status:'queued'}):wait.promise;
  const ask=el('askEvidence').onclick();await flush();await refresh();
  wait.resolve({status:'ready',result:{reply:'Recovered answer'}});await ask;
  assert.equal(el('evidenceAnswer').textContent,'Recovered answer');assert.equal(reads(),1);return;
 }
 if(scenario==='upload'){
  handler=async(url,options)=>response(url==='/evidence/files'?(options.method==='POST'?{id:'new'}:{files:[doc('doc'),doc('new')]}):doc('new'));
  await context.window.lEvidenceUpload({size:1});assert.equal(el('evidenceFiles').value,'new');assert.equal(el('evidencePage').value,1);
  assert.equal(el('evidencePreview').textContent,'new page one');assert.equal(el('evidenceAnswer').textContent,'');return;
 }
 if(['race','race_error','page'].includes(scenario)){
  const old=deferred();handler=()=>old.promise;const first=refresh();
  if(scenario==='page'){el('evidencePage').value=1;el('evidencePage').onchange();el('evidenceAnswer').textContent='Newer page answer';}
  else{handler=async()=>response({files:[doc('doc'),doc('new')]});await refresh();}
  if(scenario==='race_error')old.reject(Error('Old error'));else old.resolve(response({files:[doc('doc')]}));await first;
  if(scenario==='page'){assert.equal(el('evidencePage').value,1);assert.equal(el('evidenceAnswer').textContent,'Newer page answer');return;}
  assert.equal(el('evidenceFiles').children.length,3);assert.equal(el('evidenceStatus').textContent,'');
 }else{
  if(scenario==='missing')handler=async()=>response({files:[]});
  if(scenario==='invalid')handler=async()=>response({files:[{}]});
  if(scenario==='envelope')handler=async()=>response({});
  if(scenario==='error')handler=async()=>{throw Error('Refresh failed');};
  await refresh();
 }
 if(scenario==='missing'){
  assert.equal(el('evidenceFiles').value,'');assert.equal(el('evidencePage').value,1);assert.equal(el('evidencePage').max,1);
  assert.equal(el('evidencePreview').textContent,'');assert.equal(el('evidenceAnswer').textContent,'');
  await el('askEvidence').onclick();assert.ok(!requests.some(r=>r.url==='/evidence/ask'));
 }else{
  assert.equal(el('evidenceFiles').value,'doc');assert.equal(el('evidencePage').value,2);assert.equal(el('evidencePage').max,2);
  assert.equal(el('evidencePreview').textContent,'doc page two');assert.equal(el('evidenceAnswer').textContent,'Previous answer');assert.equal(reads(),1);
 }
 assert.equal(el('evidenceQuestion').value,'Draft question');
})().catch(e=>{console.error(e);process.exitCode=1;});

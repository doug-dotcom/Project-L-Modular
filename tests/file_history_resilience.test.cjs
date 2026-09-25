const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scenario=process.argv[2],elements=new Map(),requests=[];let initialise,handler;
const element=()=>({value:'',textContent:'',disabled:false,children:[],replaceChildren(...n){this.children=n;},appendChild(n){this.children.push(n);}});
const el=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
const task=id=>({request_id:id,status:'ready',request:{question:id+' question'}});
const response=tasks=>({ok:true,json:async()=>({tasks})});
const deferred=()=>{let resolve,reject;const promise=new Promise((y,n)=>{resolve=y;reject=n;});return{promise,resolve,reject};};
const context={AbortController,setTimeout,clearTimeout,performance:{now:()=>0},
 document:{documentElement:{dataset:{account:'ready'}},addEventListener(_,fn){initialise=fn;},getElementById:el,createElement:element},
 window:{addEventListener(){}},MutationObserver:class{observe(){}},sessionStorage:{getItem:()=>null},
 fetch:(url,options)=>{requests.push({url,options});return handler();},
 fetchChatJson:async(url,options)=>{requests.push({url,options});return{status:'ready',result:{reply:'Recovered selected answer'}};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
const history=()=>el('evidenceHistory').onclick();
(async()=>{
 handler=async()=>response([task('original')]);await history();const original=el('evidenceTasks').children[0];
 if(['missing','wrong','failure'].includes(scenario)){
  handler=async()=>{if(scenario==='failure')throw Error('Connection failed.');return{ok:true,json:async()=>scenario==='missing'?{}:{tasks:{}}};};
  await history();assert.equal(el('evidenceTasks').children[0],original);assert.match(el('evidenceStatus').textContent,/displayed list has been kept/);
 }else if(['race','race_error','answer'].includes(scenario)){
  const old=deferred();handler=()=>old.promise;const first=history();
  if(scenario==='answer')await original.onclick();
  else{handler=async()=>response([task('newer')]);await history();}
  const text=el('evidenceStatus').textContent;
  if(scenario==='race_error')old.reject(Error('Stale failure'));else old.resolve(response([task('older')]));
  await first;assert.equal(el('evidenceStatus').textContent,text);
  if(scenario==='answer')assert.equal(el('evidenceAnswer').textContent,'Recovered selected answer');
  else assert.equal(el('evidenceTasks').children[0].textContent,'newer question — ready');
 }else{
  const bad=[null,{},task(''),{...task('x'),request:null},{...task('x'),request:{question:7}},{...task('x'),status:{}}];
  const tasks=scenario==='empty'?[]:scenario==='allbad'?bad:[task('first'),...bad,task('last')];
  handler=async()=>response(tasks);await history();
  assert.equal(el('evidenceTasks').children.length,scenario==='mixed'?2:0);
  if(scenario==='empty')assert.match(el('evidenceStatus').textContent,/No saved file answers/);
  else assert.match(el('evidenceStatus').textContent,/6 entries could not be read/);
  if(scenario==='mixed'){
   assert.equal(el('evidenceTasks').children[1].textContent,'last question — ready');
   await el('evidenceTasks').children[1].onclick();assert.equal(requests.at(-1).url,'/evidence/tasks/last');
   assert.equal(el('evidenceAnswer').textContent,'Recovered selected answer');
  }
 }
 assert.ok(requests.every(r=>!r.options?.method||r.options.method==='GET'),'History must not submit a question');
})().catch(e=>{console.error(e);process.exitCode=1;});

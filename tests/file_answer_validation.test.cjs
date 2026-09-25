const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scenario=process.argv[2],elements=new Map(),storage=new Map(),voices=[],requests=[];
const id='11111111-1111-4111-8111-111111111111',key='l-evidence-pending';let initialise;
const el=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',disabled:false});return elements.get(id);};
const valid={reply:'Readable answer',evidence:{filename:'notes.pdf',page:1,quotes:['Source text']}};
const answers={missing:null,blank:{reply:'  '},number:{reply:123},array:['bad'],source:{reply:'Answer',evidence:'bad'},quotes:{...valid,evidence:{...valid.evidence,quotes:'bad'}},quoteitem:{...valid,evidence:{...valid.evidence,quotes:[{}]}},page:{...valid,evidence:{...valid.evidence,page:0}},filename:{...valid,evidence:{...valid.evidence,filename:''}},error:{reply:'Error answer',error:true},valid,failed:null};
let result={status:scenario==='failed'?'failed':'ready',result:answers[scenario]};
const context={AbortController,setTimeout,clearTimeout,performance:{now:()=>0},crypto:{randomUUID:()=>id},
 document:{documentElement:{dataset:{account:'ready'}},addEventListener(_,fn){initialise=fn;},getElementById:el},
 window:{addEventListener(){},lVoice:{onReply:reply=>voices.push(reply)}},MutationObserver:class{observe(){}},
 sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 fetch:async()=>({ok:true,json:async()=>({id:'doc',page_count:1,pages:[{text:'Page text'}]})}),
 fetchChatJson:async(url,options={})=>{requests.push({url,options});return url==='/evidence/ask'?{status:'queued'}:result;}};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
(async()=>{
 el('evidenceFiles').value='doc';await el('evidenceFiles').onchange();el('evidenceQuestion').value='Question';
 await el('askEvidence').onclick();assert.equal(el('askEvidence').disabled,false);assert.equal(requests.length,2);
 if(scenario==='valid'){
  assert.match(el('evidenceAnswer').textContent,/Readable answer.*\n\nSource: notes.pdf, physical page 1/);
  assert.match(el('evidenceStatus').textContent,/Answer recovered/);assert.equal(storage.has(key),false);assert.deepEqual(voices,['Readable answer']);
 }else if(scenario==='failed'){
  assert.match(el('evidenceStatus').textContent,/did not complete/);assert.equal(storage.has(key),false);
 }else{
  assert.equal(el('evidenceAnswer').textContent,'');assert.deepEqual(voices,[]);
  assert.match(el('evidenceStatus').textContent,/could not be read.*kept.*Saved file answers/);
  assert.equal(JSON.parse(storage.get(key)).request_id,id);assert.equal(el('evidenceQuestion').value,'Question');
 }
})().catch(e=>{console.error(e);process.exitCode=1;});

const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scenario=process.argv[2],elements=new Map(),requests=[],storage=new Map();let initialise,storageReads=0;
const key='l-evidence-pending',id='11111111-1111-4111-8111-111111111111';
const old=JSON.stringify({request_id:'22222222-2222-4222-8222-222222222222',document_id:'older',page:1,question:'Earlier question'});storage.set(key,old);
const el=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',disabled:false});return elements.get(id);};
const invalid={blank:'',space:' ',zero:'0',negative:'-1',fraction:'1.5',beyond:'3',nan:'bad',infinity:'Infinity',serverlimit:'31'};
const allowed=['first','last','boundary','unicode','trimmed'].includes(scenario);
const context={AbortController,setTimeout,clearTimeout,performance:{now:()=>0},crypto:{randomUUID:()=>id},
 document:{documentElement:{dataset:{account:'ready'}},addEventListener(_,fn){initialise=fn;},getElementById:el},
 window:{addEventListener(){}},MutationObserver:class{observe(){}},
 sessionStorage:{getItem(k){storageReads++;return storage.get(k)??null;},setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 fetch:async()=>({ok:true,json:async()=>({id:'doc',page_count:scenario==='serverlimit'?40:2,pages:[{text:'Page one'},{text:'Page two'}]})}),
 fetchChatJson:async(url,options={})=>{requests.push({url,options});return url==='/evidence/ask'?{status:'queued'}:{status:'ready',result:{reply:'Answer'}};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
(async()=>{
 el('evidenceFiles').value='doc';await el('evidenceFiles').onchange();el('evidenceAnswer').textContent='Previous answer';
 el('evidencePage').value=invalid[scenario]??(scenario==='last'?'2':'1');
 const question=scenario==='long'?'x'.repeat(4001):scenario==='boundary'?'x'.repeat(4000):scenario==='unicode'?'😀'.repeat(4000):scenario==='trimmed'?'  '+'x'.repeat(4000)+'  ':'Keep my question';
 el('evidenceQuestion').value=question;await el('askEvidence').onclick();
 if(!allowed){
  assert.equal(requests.length,0);assert.equal(storageReads,0);assert.equal(storage.get(key),old);
  assert.equal(el('evidenceAnswer').textContent,'Previous answer');assert.equal(el('evidenceQuestion').value,question);
  assert.equal(el('evidencePreview').textContent,'Page one');assert.equal(el('askEvidence').disabled,false);
  assert.match(el('evidenceStatus').textContent,scenario==='long'?/4,000 characters/:/whole page number/);
  el('evidencePage').value='2';el('evidenceQuestion').value='Corrected question';await el('askEvidence').onclick();
 }
 assert.equal(requests.length,2);const body=JSON.parse(requests[0].options.body);
 assert.equal(body.page,allowed?(scenario==='last'?2:1):2);assert.equal(body.question,allowed?question.trim():'Corrected question');
 assert.equal(el('askEvidence').disabled,false);assert.equal(el('evidenceAnswer').textContent,'Answer');
 assert.equal(storage.has(key),false);
})().catch(e=>{console.error(e);process.exitCode=1;});

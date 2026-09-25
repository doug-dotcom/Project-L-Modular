const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const scenario=process.argv[2], elements=new Map(), storage=new Map(), requests=[], key='l-evidence-pending';
const savedId='11111111-1111-4111-8111-111111111111', freshId='22222222-2222-4222-8222-222222222222';
let initialise, fail=true, ids=0;
const el=id=>{if(!elements.has(id)) elements.set(id,{value:'',textContent:'',disabled:false,children:[],replaceChildren(...n){this.children=n;},add(n){this.children.push(n);},appendChild(n){this.children.push(n);}});return elements.get(id);};
const candidate={document_id:'doc',page:1,question:'Keep this question'};
const existing={...candidate,request_id:savedId,unexpected:'Do not forward'};
const invalid={json:'{broken',null:'null',array:'[]',number:'42',missing:JSON.stringify(candidate),invalid:JSON.stringify({...existing,request_id:'bad/id'})};
if(scenario in invalid) storage.set(key,invalid[scenario]);
if(['reuse','different','write'].includes(scenario)) storage.set(key,JSON.stringify({...existing,question:scenario==='different'?'Earlier question':candidate.question}));
const before=storage.get(key);
const context={
    AbortController,setTimeout,clearTimeout,performance:{now:()=>0},
    crypto:{randomUUID(){ids++;if(fail&&scenario==='uuid') throw Error('PRIVATE generator failure');return fail&&scenario==='uuidinvalid'?'invalid':freshId;}},
    document:{documentElement:{dataset:{account:'ready'}},addEventListener(_,fn){initialise=fn;},getElementById:el},
    window:{addEventListener(){}},MutationObserver:class{observe(){}},
    sessionStorage:{getItem(k){if(fail&&scenario==='read')throw Error('PRIVATE storage read');return storage.get(k)??null;},setItem(k,v){if(fail&&scenario==='write')throw Error('PRIVATE storage write');storage.set(k,v);},removeItem(k){storage.delete(k);}},
    fetch:async()=>({ok:true,json:async()=>({id:'doc',page_count:1,pages:[{text:'Page one'}]})}),
    fetchChatJson:async(url,options={})=>{requests.push({url,options});return url==='/evidence/ask'?{status:'queued'}:{status:'ready',result:{reply:'New answer'}};}
};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
(async()=>{
    el('evidenceFiles').value='doc';await el('evidenceFiles').onchange();
    el('evidenceQuestion').value='  Keep this question  ';el('evidenceAnswer').textContent='Previous answer';
    await el('askEvidence').onclick();
    if(!['reuse','different'].includes(scenario)){
        assert.equal(requests.length,0,'Failed preparation must not submit or poll');
        assert.equal(el('askEvidence').disabled,false);assert.equal(el('evidenceQuestion').value,'  Keep this question  ');
        assert.equal(el('evidenceAnswer').textContent,'Previous answer');assert.equal(el('evidencePreview').textContent,'Page one');
        assert.equal(storage.get(key),before,'Do not overwrite unreadable recovery details');
        assert.match(el('evidenceStatus').textContent,/not sent.*still here.*Saved file answers/);
        assert.ok(!el('evidenceStatus').textContent.includes('PRIVATE'));
        // Simulate the underlying preparation problem being resolved before an explicit retry.
        fail=false;storage.delete(key);await el('askEvidence').onclick();
    }
    const posts=requests.filter(r=>r.url==='/evidence/ask');assert.equal(posts.length,1);
    const body=JSON.parse(posts[0].options.body);
    assert.deepEqual(body,{...candidate,request_id:scenario==='reuse'?savedId:freshId});
    assert.equal(requests.length,2);assert.ok(requests[1].url.endsWith(body.request_id));
    assert.equal(el('askEvidence').disabled,false);assert.equal(el('evidenceAnswer').textContent,'New answer');
    assert.equal(storage.has(key),false);if(scenario==='reuse')assert.equal(ids,0);
})().catch(e=>{console.error(e);process.exitCode=1;});

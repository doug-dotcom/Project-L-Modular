const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('ui/recovery-status.js', 'utf8');
const {describe} = require('../ui/recovery-status.js');
const scenario = process.argv[2];
function report(status = 'ready') {
    return {mode:'durable_recovery_readiness', status, recovery_ready:status.startsWith('ready'),
        scan_complete:status !== 'incomplete_scan', capped:false,
        checks:{ledger_consistent:true, all_observed_tasks_certified:true},
        task_ledger:{tasks_observed:2}, saved_answers:{certified_answers:2,not_ready_answers:0}};
}
function harness() {
    let start, onMutation;
    const elements = new Map(), events = {}, calls = [];
    const element = () => ({children:[],disabled:false,textContent:'',attributes:{},
        setAttribute(k,v){this.attributes[k]=v;}, replaceChildren(){this.children=[];},
        append(...els){for(const el of els){el.removed=false;if(!this.children.includes(el))this.children.push(el);}},
        focus(){this.focused=true;}, remove(){this.removed=true;}});
    const get = id => {if(!elements.has(id))elements.set(id,element());return elements.get(id);};
    const root = {dataset:{account:'ready'}};
    const h = {get,root,calls,events,token:'fixture-owner',response:report(),
        text:()=>get('chat').children.filter(c=>!c.removed).flatMap(c=>c.children.map(x=>x.textContent)).join('\n'),
        mutate:()=>onMutation()};
    vm.runInNewContext(source, {
        document:{documentElement:root,getElementById:get,createElement:element,addEventListener:(_,fn)=>{start=fn;}},
        window:{addEventListener:(key,fn)=>events[key]=fn,lChatTools:{close(){}}},
        MutationObserver:class {constructor(fn){onMutation=fn;} observe(){}},
        localStorage:{getItem:()=>h.token},
        fetchChatJson:async(...args)=>{calls.push(args);if(h.fail)throw Error('PRIVATE backend error');return h.wait ? h.wait : h.response;}
    });
    start(); return h;
}
(async()=>{
    if (['ready','ready_with_legacy','pending_tasks','needs_attention','incomplete_scan','no_tasks'].includes(scenario)) {
        const h=harness();h.response=report(scenario);
        h.response.injected='PRIVATE';
        await h.get('checkSavedAnswersAction').onclick();
        assert.equal(h.calls.length,1);
        assert.equal(h.calls[0][1].method,'GET');
        assert.equal(h.calls[0][1].cache,'no-store');
        assert.equal(h.calls[0][1].headers['X-L-Recovery-Token'],'fixture-owner');
        assert.equal(h.calls[0][2],30000);
        assert.match(h.text(),/Tasks checked: 2/);
        assert.ok(!h.text().includes('PRIVATE'));
        assert.ok(!h.text().includes('fixture-owner'));
        assert.equal(h.get('checkSavedAnswersAction').disabled,false);
        assert.equal(h.get('chat').children[0].attributes['role'],'status');
        assert.equal(h.get('chat').children[0].focused,true);
    } else if(scenario==='invalid') {
        for(const bad of [null,{}, {...report(),status:'<img src=x>'}, {...report(),scan_complete:false},
            {...report(),saved_answers:{certified_answers:'PRIVATE',not_ready_answers:0}},
            {...report(),task_ledger:{tasks_observed:1}}, {...report(),checks:{ledger_consistent:false}}])
            assert.throws(()=>describe(bad));
        const h=harness();h.response={status:'PRIVATE'};
        await h.get('checkSavedAnswersAction').onclick();
        assert.match(h.text(),/could not finish/);assert.ok(!h.text().includes('PRIVATE'));
    } else if(scenario==='on_demand') {
        const h=harness();assert.equal(h.calls.length,0);
        h.token=null;await h.get('checkSavedAnswersAction').onclick();
        assert.equal(h.calls.length,0);assert.match(h.text(),/No recovery link/);
    } else if(scenario==='retry') {
        const h=harness();await h.get('checkSavedAnswersAction').onclick();
        h.fail=true;await h.get('checkSavedAnswersAction').onclick();
        assert.match(h.text(),/could not finish/);assert.ok(!h.text().includes('passed recovery'));
        assert.equal(h.get('checkSavedAnswersAction').disabled,false);
        h.fail=false;await h.get('checkSavedAnswersAction').onclick();
        assert.match(h.text(),/passed recovery checks/);assert.equal(h.get('chat').children.length,1);
    } else if(scenario==='duplicate') {
        const h=harness();let resolve;h.wait=new Promise(r=>resolve=r);
        const first=h.get('checkSavedAnswersAction').onclick();
        await h.get('checkSavedAnswersAction').onclick();assert.equal(h.calls.length,1);
        resolve(report());await first;assert.equal(h.get('checkSavedAnswersAction').disabled,false);
    } else if(scenario==='account_change' || scenario==='account_locked') {
        const h=harness();let resolve;h.wait=new Promise(r=>resolve=r);
        const first=h.get('checkSavedAnswersAction').onclick();
        if(scenario==='account_change')h.events['l-account-ready']();
        else {h.root.dataset.account='locked';h.mutate();}
        resolve(report());await first;assert.equal(h.text(),'');
    } else throw Error('Unknown scenario');
    console.log(scenario+' passed');
})().catch(e=>{console.error(e);process.exitCode=1;});

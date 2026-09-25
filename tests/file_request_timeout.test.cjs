const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const [operation, mode] = process.argv[2].split('_');
const elements = new Map(), timers = new Map(), requests = [], root = {dataset: {account:'ready'}};
let initialise, mutation, now = 0, timerId = 0, aborted = 0, downloads = 0, phase = 'setup', late;
const element = () => ({value:'', textContent:'', disabled:false, children:[],
    replaceChildren(...n) {this.children=n;}, appendChild(n) {this.children.push(n);}, add(n) {this.children.push(n);}, click() {}, remove() {}});
const el = id => {if (!elements.has(id)) elements.set(id,element()); return elements.get(id);};
const doc = {id:'doc',filename:'file.pdf',page_count:1,pages:[{text:'Saved page'}]};
const value = url => url.endsWith('/original') ? {bytes:'file'} : url === '/evidence/tasks' ? {tasks:[]} : url === '/evidence/files' ? {id:'doc',files:[doc]} : doc;
const response = url => ({ok:true,json:async()=>value(url),blob:async()=>value(url)});
const context = {
    AbortController, FormData:class {append() {}},
    document:{documentElement:root,addEventListener(_,fn) {initialise=fn;},getElementById:el,createElement:element,body:element()},
    window:{addEventListener() {}}, MutationObserver:class {constructor(fn) {mutation=fn;} observe() {}},
    Option:class {constructor(text,value) {this.text=text;this.value=value;}},
    URL:{createObjectURL() {downloads++;return 'blob:fixture';},revokeObjectURL() {}},
    setTimeout(fn,delay) {const id=++timerId;timers.set(id,{fn,at:now+delay});return id;},clearTimeout:id=>timers.delete(id),
    fetch:async(url,options={})=>{
        requests.push({url,options}); options.signal?.addEventListener('abort',()=>aborted++);
        if (phase !== 'stall') return response(url);
        if (mode === 'error') return {ok:false,json:async()=>({detail:'Choose a supported file.'})};
        const hung = () => new Promise(resolve=>{late=()=>resolve(mode==='body'?value(url):response(url));});
        return mode === 'body' ? {ok:true,json:hung,blob:hung} : hung();
    }
};
vm.createContext(context);vm.runInContext(fs.readFileSync('ui/evidence.js','utf8'),context);initialise();
const flush = () => new Promise(setImmediate);
async function drive(promise) {
    let done=false,error;promise.then(()=>done=true,e=>{error=e;done=true;});
    for(let i=0;i<20&&!done;i++) {
        await flush();if(done) break;
        const next=[...timers].sort((a,b)=>a[1].at-b[1].at)[0];assert.ok(next,'Missing timeout');
        timers.delete(next[0]);now=next[1].at;next[1].fn();
    }
    assert.ok(done,'Request remained stuck');if(error) throw error;
}
const upload=()=>context.window.lEvidenceUpload({size:100});
const start=()=> operation==='upload'?upload():operation==='list'?el('refreshFiles').onclick():operation==='history'?el('evidenceHistory').onclick():operation==='download'?el('openOriginal').onclick():el('evidenceFiles').onchange();
(async()=>{
    el('evidenceFiles').value='doc';await el('evidenceFiles').onchange();
    el('evidenceQuestion').value='Keep my question'; phase='stall';
    const pending=start();await flush();
    if(mode==='locked') {root.dataset.account='locked';mutation();}
    await drive(pending);
    assert.equal(timers.size,0);assert.equal(downloads,0);
    assert.equal(requests.filter(r=>r.options.method==='POST').length,operation==='upload'?1:0);
    if(mode==='error') {
        assert.match(el('evidenceStatus').textContent,/Choose a supported file/);assert.equal(aborted,0);
    } else {
        assert.equal(now,operation==='upload'?60000:operation==='download'?30000:15000);
        assert.equal(aborted,1);
        if(mode==='locked') assert.equal(el('evidenceStatus').textContent,'');
        else assert.match(el('evidenceStatus').textContent,operation==='upload'?/may still finish saving.*Refresh/:/timed out/);
        const before=JSON.stringify([...elements].map(([id,e])=>[id,e.textContent,e.value]));
        late();await flush();
        assert.equal(JSON.stringify([...elements].map(([id,e])=>[id,e.textContent,e.value])),before);
        assert.equal(downloads,0);assert.equal(timers.size,0);
    }
    if(mode!=='locked') assert.equal(el('evidenceQuestion').value,'Keep my question');
    if(operation==='upload'&&mode!=='locked') {
        // An explicit later upload is possible: timeout released the busy state.
        phase='success';await upload();
        assert.equal(requests.filter(r=>r.options.method==='POST').length,2);
        assert.match(el('evidenceStatus').textContent,/saved to your account/);
        assert.equal(el('evidencePreview').textContent,'Saved page');assert.equal(timers.size,0);
    }
})().catch(e=>{console.error(e);process.exitCode=1;});

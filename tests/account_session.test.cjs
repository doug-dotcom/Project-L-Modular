const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const listeners = [], storage = new Map(), elements = new Map(), calls = [];
const buttons = [{},{}];
function element(id) {
    if (!elements.has(id)) elements.set(id,{id,value:'',textContent:'',reportValidity:()=>true,querySelectorAll:()=>buttons});
    return elements.get(id);
}
let deny=false, refreshCount=0;
const nativeFetch = async (url,options={}) => {
    calls.push({url,options});
    if (url==='/account/login') return Response.json({access_token:'owner-token',refresh_token:'refresh',expires_in:3600});
    if (url==='/account/refresh') { refreshCount++; await new Promise(r=>setTimeout(r,5)); return Response.json({access_token:'refreshed-token',refresh_token:'next',expires_in:3600}); }
    if (url==='/account/me') return Response.json({user_id:'owner-id'}, {status:deny?403:200});
    return Response.json({ok:true});
};
const location={href:'https://l.example/',origin:'https://l.example',reload(){this.reloaded=true;}};
const document={documentElement:{dataset:{}},getElementById:element,
    createElement:()=>({}),body:{appendChild(){}},addEventListener:(name,fn)=>listeners.push(fn)};
const window={fetch:nativeFetch,dispatchEvent(){}};
const context={window,document,location,sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    URL,Headers,Request,Response,AbortSignal,CustomEvent:class {},console};
vm.createContext(context);
vm.runInContext(fs.readFileSync('ui/account.js','utf8'),context);
(async()=>{
    await listeners[0]();
    assert.equal(document.documentElement.dataset.account,'locked');
    assert.equal((await window.fetch('/evidence/files')).status,401);
    assert.equal(calls.filter(x=>x.url==='/evidence/files').length,0);
    element('accountEmail').value='owner@example.com'; element('accountPassword').value='synthetic-password';
    element('accountForm').onsubmit({preventDefault(){}});
    await new Promise(r=>setTimeout(r,10));
    assert.equal(document.documentElement.dataset.account,'ready');
    assert.equal(element('accountPassword').value,'');
    await window.fetch('/evidence/files');
    assert.equal(calls.at(-1).options.headers.get('Authorization'),'Bearer owner-token');
    await window.fetch('https://untrusted.example/');
    assert.equal(calls.at(-1).options.headers,undefined);
    // Forbidden responses lock the UI instead of presenting an authenticated page.
    deny=true;
    element('accountPassword').value='synthetic-password';element('accountForm').onsubmit({preventDefault(){}});
    await new Promise(r=>setTimeout(r,10));
    assert.equal(document.documentElement.dataset.account,'locked');
    assert.equal(refreshCount,0);
    console.log('Account session UI: unauthenticated requests blocked, bearer restricted to same origin, sign-in and account rejection passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

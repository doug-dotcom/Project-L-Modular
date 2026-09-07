const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup(hash='', valid=true) {
    const elements=new Map(), listeners=[], calls=[], storage=new Map();
    const element=id=>{
        if(!elements.has(id)) elements.set(id,{value:'',hidden:id==='resetPasswordForm',reportValidity:()=>true,querySelectorAll:()=>[]});
        return elements.get(id);
    };
    const location={href:'https://l.example/'+hash,origin:'https://l.example',reload(){}};
    const window={history:{replaceState(a,b,url){location.href=url;}},dispatchEvent(){},fetch:async(url,options={})=>{
        calls.push({url,options});
        if(url==='/account/me') return Response.json({user_id:'owner'},{status:valid?200:403});
        if(url==='/account/password') return Response.json({password_updated:true,signed_out:true});
        if(url==='/account/recover') return Response.json({message:'Check your email'});
        throw Error('Unexpected request: '+url);
    }};
    const document={documentElement:{dataset:{}},getElementById:element,createElement:()=>({}),body:{appendChild(){}},addEventListener:(name,fn)=>listeners.push(fn)};
    vm.runInNewContext(fs.readFileSync('ui/account.js','utf8'),{window,document,location,URL,URLSearchParams,Headers,Request,Response,AbortSignal,
        sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}});
    return {element,window,document,location,calls,storage,start:listeners[0]};
}
(async()=>{
    const r=setup('#access_token=synthetic-recovery&refresh_token=secret&type=recovery');
    assert.equal(r.location.href,'https://l.example/');
    assert.equal(r.storage.size,0);
    await r.start();
    assert.equal(r.element('resetPasswordForm').hidden,false);
    assert.equal(r.element('accountForm').hidden,true);
    assert.equal(r.document.documentElement.dataset.account,'locked');
    assert.equal((await r.window.fetch('/evidence/files')).status,401);
    r.element('newLPassword').value='new-test-password';
    r.element('confirmLPassword').value='different';
    await r.element('resetPasswordForm').onsubmit({preventDefault(){}});
    assert.equal(r.calls.filter(x=>x.url==='/account/password').length,0);
    r.element('confirmLPassword').value='new-test-password';
    await r.element('resetPasswordForm').onsubmit({preventDefault(){}});
    const save=r.calls.find(x=>x.url==='/account/password');
    assert.equal(save.options.headers.Authorization,'Bearer synthetic-recovery');
    assert.deepEqual(JSON.parse(save.options.body),{password:'new-test-password'});
    assert.equal(r.element('resetPasswordForm').hidden,true);
    assert.equal(r.element('accountForm').hidden,false);
    assert.equal(r.element('newLPassword').value,'');
    assert.equal(r.storage.size,0);
    assert.match(r.element('accountStatus').textContent,/Password updated/);
    const expired=setup('#error=access_denied&error_code=otp_expired&error_description=untrusted');
    await expired.start();
    assert.equal(expired.location.href,'https://l.example/');
    assert.match(expired.element('accountStatus').textContent,/expired/);
    assert.equal(expired.calls.length,0);
    const denied=setup('#access_token=wrong-account&type=recovery',false); await denied.start();
    assert.equal(denied.element('resetPasswordForm').hidden,true);
    assert.match(denied.element('accountStatus').textContent,/not valid/);
    const forgot=setup(); await forgot.start();
    forgot.element('accountEmail').value='owner@example.com';
    await forgot.element('forgotLPassword').onclick();
    assert.deepEqual(JSON.parse(forgot.calls.at(-1).options.body),{email:'owner@example.com'});
    assert.equal(forgot.calls.at(-1).options.headers.Authorization,undefined);
    console.log('Recovery UI: token removal, validation, isolation, expired links, mismatch and successful reset passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});

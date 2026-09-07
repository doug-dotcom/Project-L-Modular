const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const page = fs.readFileSync('ui/index.html','utf8');
assert.ok(!page.includes('chat.parentElement.insertBefore(button, chat)'));
assert.ok(page.includes("document.getElementById('chatToolsActions').insertBefore(button"));
assert.equal((page.match(/href="\/ui\/shine-l-icon\.png\?v=1"/g)||[]).length,2);
assert.ok(fs.existsSync('ui/shine-l-icon.png'));
const elements = new Map();
const el = id => {
    if (!elements.has(id)) elements.set(id, {hidden:true, open:false, attributes:{}, handlers:{},
        setAttribute(k,v){this.attributes[k]=v;}, focus(){this.focused=true;},
        click(){this.clicked=true;}, addEventListener(k,fn){this.handlers[k]=fn;}});
    return elements.get(id);
};
let start;
const window = {};
vm.runInNewContext(fs.readFileSync('ui/chat-tools.js','utf8'), {
    window, document:{getElementById:el,addEventListener:(name,fn)=>{start=fn;}}
});
start();
assert.equal(el('chatTools').hidden,true);
el('uploadBtn').onclick();
assert.equal(el('chatTools').hidden,false);
assert.equal(el('uploadBtn').attributes['aria-expanded'],'true');
assert.equal(el('evidencePanel').hidden,true);
assert.equal(el('voicePanel').hidden,true);
el('attachFileAction').onclick();
assert.equal(el('fileInput').clicked,true);
el('privateFilesAction').onclick();
assert.equal(el('evidencePanel').hidden,false);
assert.equal(el('evidencePanel').open,true);
el('spokenAction').onclick();
assert.equal(el('voicePanel').hidden,false);
assert.equal(el('voicePanel').open,true);
assert.equal(el('evidencePanel').hidden,true);
el('chatTools').handlers.keydown({key:'Escape',preventDefault(){}});
assert.equal(el('chatTools').hidden,true);
assert.equal(el('uploadBtn').focused,true);
assert.equal(el('voicePanel').open,true); // Closing does not discard recording state.
window.lChatTools.show('files'); // Uploading opens the saved-file view.
assert.equal(el('chatTools').hidden,false);
assert.equal(el('evidencePanel').hidden,false);
assert.equal(el('voicePanel').hidden,true);
el('closeChatTools').onclick();
assert.equal(el('chatTools').hidden,true);
assert.equal(el('uploadBtn').attributes['aria-expanded'],'false');
console.log('Chat tools: collapsed default, upload, file/voice selection, Escape and focus passed.');

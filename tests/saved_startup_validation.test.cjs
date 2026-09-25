const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('ui/index.html','utf8'),source=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes('const API_URL'));
const scenario=process.argv[2],storage=new Map(),checked=[],buttons=[];
const values={null:null,object:{requestId:'not-an-array'},mixed:[null,{},19,{requestId:2},{requestId:'  '},{requestId:'one',pending:true},{requestId:'two',pending:true}],legacy:[]};
storage.set('project-l-saved-tasks',JSON.stringify(values[scenario]));
storage.set('project-l-pending-request',JSON.stringify({requestId:scenario==='legacy'?'old':42}));
const original=JSON.stringify([...storage]);
const context={window:{},document:{addEventListener(){},createElement:()=>({}),getElementById:()=>({insertBefore:b=>buttons.push(b)})},
 localStorage:{getItem:k=>storage.get(k)||null,setItem(){throw Error('Unexpected write')},removeItem(){throw Error('Unexpected removal')}}};
vm.createContext(context);vm.runInContext(source,context);
let installed=0;context.installSavedAnswerReview=()=>installed++;
context.appendChatMessage=()=>({remove(){}});context.clearPendingRequest=()=>{};
context.recoverChatResponse=async id=>{checked.push(id);return {reply:'Recovered'}};
(async()=>{
 await context.resumePendingRequest();
 assert.equal(installed,1);assert.equal(buttons[0].id,'savedAnswersAction');
 assert.deepEqual(checked,scenario==='mixed'?['one','two']:scenario==='legacy'?['old']:[]);
 assert.equal(JSON.stringify([...storage]),original);
})().catch(err=>{console.error(err);process.exitCode=1});

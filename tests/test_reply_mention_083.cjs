'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

// Evaluate exactly the production Reply functions, not a second implementation.
const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const start=app.indexOf('function resolveDirectSender082(');
const end=app.indexOf("$('all-messages').addEventListener",start);
assert.ok(start>=0 && end>start);
const code=app.slice(start,end);

function scenario(message,initial='',contacts=[],options=['channel:0','channel:1','channel:2']){
 const nodes={
  destination:{value:'channel:1',options:options.map(value=>({value}))},
  'message-text':{value:initial,maxLength:180,dispatchEvent(){this.changed=true},scrollIntoView(){},focus(){this.focused=true},setSelectionRange(a,b){this.cursor=[a,b]}},
  'reply-context':{hidden:true},
  'reply-context-label':{textContent:''}
 };
 const calls=[];
 const context={
  S:{contacts},M081:{items:[{id:99,direction:'in',...message}]},
  $:id=>nodes[id],
  toast:(...args)=>calls.push(['toast',...args]),
  confirm:(...args)=>{calls.push(['confirm',...args]);return true},
  short:s=>s,
  Event:class{constructor(type){this.type=type}}
 };
 vm.createContext(context);
 vm.runInContext(code,context);
 context.createReply082(99);
 return {nodes,calls};
}

// Channel 0 is the default Public channel; do not accidentally treat numeric zero as missing.
for(const target of ['0',0]){
 const x=scenario({kind:'channel',target,sender:'channel',text:'HamHock: Are you receiving?'},'testing');
 assert.equal(x.nodes.destination.value,'channel:0');
 assert.equal(x.nodes['message-text'].value,'@HamHock testing');
 assert.equal(x.nodes['reply-context'].hidden,false);
 assert.equal(x.nodes['message-text'].focused,true);
 assert.equal(x.nodes['message-text'].changed,true);
 assert.deepEqual(x.calls[0][0],'confirm');
}

// A channel's displayed sender is often embedded in its text envelope, not m.sender.
{
 const x=scenario({kind:'channel',target:'2',sender:'channel',text:'North Ridge Repeater: Hello'});
 assert.equal(x.nodes.destination.value,'channel:2');
 assert.equal(x.nodes['message-text'].value,'@North Ridge Repeater ');
}
// Avoid double-appending the same @mention to an existing draft.
{
 const x=scenario({kind:'channel',target:'0',sender:'channel',text:'HamHock: Reply? '},'@HamHock My draft');
 assert.equal(x.nodes['message-text'].value,'@HamHock My draft');
}
// Channel events without a parseable name should not mention the generic word 'channel'.
{
 const x=scenario({kind:'channel',target:'0',sender:'channel',text:'No sender prefix on this message'},'draft');
 assert.equal(x.nodes['message-text'].value,'draft');
 assert.match(x.nodes['reply-context-label'].textContent,/sender name unavailable/);
}
// A direct reply must still resolve to exactly one radio contact; it does not add an @mention.
{
 const key='a'.repeat(64);
 const x=scenario({kind:'direct',target:'',sender:key.slice(0,12),text:'Hello'},'draft', [{name:'HamHock',key}], ['channel:0',key]);
 assert.equal(x.nodes.destination.value,key);
 assert.equal(x.nodes['message-text'].value,'draft');
}
// Length validation keeps the existing draft and destination unchanged.
{
 const x=scenario({kind:'channel',target:'0',sender:'channel',text:'HamHock: hello'},'x'.repeat(179));
 assert.equal(x.nodes.destination.value,'channel:1');
 assert.equal(x.nodes['message-text'].value,'x'.repeat(179));
 assert.equal(x.nodes['reply-context'].hidden,true);
 assert.match(x.calls.at(-1)[1],/exceeds/);
}
console.log('6 reply scenarios passed, including numeric/string Channel 0, embedded usernames, drafts, direct replies, and length guard');

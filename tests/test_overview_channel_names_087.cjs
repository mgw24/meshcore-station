'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const code=fs.readFileSync('static/app.js','utf8');
function section(start,end){const a=code.indexOf(start),b=code.indexOf(end,a);assert(a>=0&&b>a,`Missing section ${start}`);return code.slice(a,b)}
const context={
 S:{status:{radio_config:{name:'MCS-T114 LewID'},channels:[{index:0,name:'Public'},{index:5,name:'LongFast'}]},channels:{slots:[]},contacts:[]},
 H:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
 dt:()=> 'Nov 17 11:36 PM',
 compactTimestamp082:()=> '11:36 PM',
 txLabel:()=> 'Radio accepted'
};
vm.createContext(context);
vm.runInContext(section('function messageHeading(m)','function item(')+'\n'+section('// 0.8.6 — Use','function renderMessageArchive081()')+'\n'+section('function resolveDirectSender082(','function createReply082('),context);
function m(d={}){return {id:15,kind:'channel',direction:'in',sender:'channel',target:5,text:'IdahoMesh Bot: Hello',ts:'2026-11-17T23:36:00Z',status:'received',tx_evidence:[],...d}}
const heading=context.messageHeading;
const archive=x=>context.messageArchiveEntry081(x).match(/<strong class="message-row-sender"[^>]*>([^<]*)<\/strong>/)?.[1];
assert.equal(heading(m()),'#5 · Received · LongFast');
assert.equal(heading(m({target:0})),'#0 · Received · Public');
assert.equal(heading(m({target:3})),'#3 · Received · Channel 3');
assert.equal(heading(m()),'#5 · Received · '+archive(m()),'Overview and archive must use the same channel name');
assert.equal(heading(m({sender:'IdahoMesh Bot'})),'#5 · Received · IdahoMesh Bot','Actual senders retained');
assert.equal(heading(m({sender:'Unknown sender'})),'#5 · Received · LongFast','Generic sender aliases resolved');
assert.equal(heading(m({kind:'direct',sender:'abc123'})),'Direct · Received · abc123','Direct messages unchanged');
assert.equal(heading(m({direction:'out',sender:'MCS-T114 LewID'})),'#5 · Sent · MCS-T114 LewID','Outbound sender unchanged');
context.S.status.channels[1].name='Renamed channel';
assert.equal(heading(m()),'#5 · Received · Renamed channel');
context.S.status.channels[1].name='<script>alert(1)</script>';
const label=heading(m());
assert(!label.includes('channel ·'), 'Should never show generic channel');
assert.equal(archive(m()),'&lt;script&gt;alert(1)&lt;/script&gt;', 'Archive escapes configurable names');
assert.match(code,/rec\.map\(m=>item\(messageHeading\(m\)/,'Overview uses updated heading');
console.log('Overview/History channel-label integration: 11 checks passed');

'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const app=fs.readFileSync('static/app.js','utf8');
function section(start,end){const a=app.indexOf(start),b=app.indexOf(end,a);assert(a>=0&&b>a,`Missing JS section ${start}`);return app.slice(a,b)}
const context={
 S:{status:{radio_config:{name:'MCS-T114 LewID'},channels:[{index:0,name:'Public'},{index:5,name:'LongFast'}]},channels:{slots:[]},contacts:[]},
 H:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
 dt:()=> 'Nov 17 11:36 PM',
 compactTimestamp082:()=> '11:36 PM',
 txLabel:()=> 'Radio accepted'
};
vm.createContext(context);
vm.runInContext(section('// 0.8.6 — Use', 'function renderMessageArchive081()') + '\n'+section('function resolveDirectSender082(', 'function createReply082('),context);
function html(data){return context.messageArchiveEntry081({id:17,ts:'2026-11-17T23:36:00Z',direction:'in',kind:'channel',target:'5',sender:'channel',text:'IdahoMesh Bot: Copy received',status:'received',tx_evidence:[],...data})}
function senderMarkup(rendered){return rendered.match(/<strong class="message-row-sender"[^>]*>([^<]*)<\/strong>/)?.[1]}
assert.equal(senderMarkup(html({target:'5'})),'LongFast','Incoming channel sender label should use configured slot 5');
assert.match(html({target:'5'}),/LongFast \(#5\)/,'Include channel name and stable slot in row and details');
assert.match(html({target:'5'}),/<dt>From<\/dt><dd>IdahoMesh Bot<\/dd>/,'Preserve actual sender from message text when available');
assert.equal(senderMarkup(html({target:'0',text:'Fur_Missile_Handler: Hello'})),'Public','Channel 0 should resolve to Public');
assert.equal(senderMarkup(html({target:'3'})),'Channel 3','Unknown/unconfigured slots get a numbered fallback');
assert.equal(senderMarkup(html({sender:'Fur_Missile_Handler'})),'Fur_Missile_Handler','Do not replace real sender identities');
assert.equal(senderMarkup(html({direction:'out',sender:'MCS-T114 LewID'})),'MCS-T114 LewID','Do not replace outbound sender name');
assert.match(html({direction:'out',sender:'MCS-T114 LewID'}),/LongFast \(#5\)/,'Outgoing messages show channel names in conversation');
assert.equal(senderMarkup(html({kind:'direct',sender:'abcd1234'})),'abcd1234','Direct messages unchanged');
context.S.status.channels[1].name='New channel';
assert.equal(senderMarkup(html({target:'5'})),'New channel','Renaming channel updates existing history labels');
context.S.status.channels[1].name='<script>alert(1)</script>';
assert.equal(senderMarkup(html({target:'5'})),'&lt;script&gt;alert(1)&lt;/script&gt;','HTML escape channel names');
assert(!html({target:'5'}).includes('<script>'),'Must not render raw HTML in channel label');
assert.match(app,/dest='channel:'\+channel/,'Reply still uses unchanged numeric slot');
assert.match(app,/if\(names!==lastChannelNames086\)/,'Refresh renamed channel labels without reloading messages');
console.log('0.8.6 channel-name behavior: 12 checks passed');

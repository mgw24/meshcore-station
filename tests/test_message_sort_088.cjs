'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const app=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
function section(start,end){const a=app.indexOf(start),b=app.indexOf(end,a);assert(a>=0&&b>a);return app.slice(a,b);}
const controls={
 'history-search':{value:'hello'},'history-direction':{value:'in'},
 'history-destination':{value:'channel:5',innerHTML:'',options:[]},'history-sort':{value:'channel_desc'}
};
const ctx={
 $:name=>controls[name],
 S:{status:{channels:[{index:0,name:'Public'},{index:5,name:'LongFast'}]},channels:{slots:[]}},
 H:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
 URLSearchParams
};
vm.createContext(ctx);
vm.runInContext(section('function fillArchiveDestinations(){','function render(){')+'\n'+section('const HISTORY_SORT_LABELS088=', 'function compactTimestamp082(')+'\n'+section('function channelName086(target)', 'function messageDisplaySender086(m)'),ctx);
const filters=ctx.messageFilters081();
assert.equal(filters.destination,'channel:5');
assert.equal(filters.sort,'channel_desc');
assert.equal(filters.direction,'in');
assert.equal(filters.q,'hello');
const url=new URL(ctx.messageQuery081(filters,{before_ts:'2026-11-22T20:00:00+00:00',before_id:20,before_channel:'5'}),'http://example');
assert.equal(url.searchParams.get('sort'),'channel_desc');
assert.equal(url.searchParams.get('destination'),'channel:5');
assert.equal(url.searchParams.get('before_channel'),'5');
function msg(kind,target,id,ts){return {kind,target,id,ts};}
const rows=[msg('direct','private',2,'2026-11-22T12:00:00Z'),msg('channel','5',8,'2026-11-22T21:00:00Z'),msg('channel','0',9,'2026-11-22T21:00:00Z'),msg('channel','5',3,'2026-11-22T21:00:00Z'),msg('channel','0',10,'2026-11-22T20:00:00Z')];
assert.deepEqual(rows.slice().sort((a,b)=>ctx.archiveCompare088(a,b,'channel_asc')).map(x=>x.id),[9,10,8,3,2]);
assert.deepEqual(rows.slice().sort((a,b)=>ctx.archiveCompare088(a,b,'channel_desc')).map(x=>x.id),[8,3,9,10,2]);
assert.deepEqual(rows.slice().sort((a,b)=>ctx.archiveCompare088(a,b,'oldest')).map(x=>x.id),[2,10,3,8,9]);
// DOM integration: the real page has both independently labeled controls and reset hook.
assert.match(html,/id="history-destination" aria-label="Filter messages by channel"/);
assert.match(html,/id="history-sort" aria-label="Sort message history"/);
assert.match(app,/\['history-direction','history-destination','history-sort'\]/);
assert.match(app,/\$\('history-sort'\)\.value='newest'/);
assert.match(app,/if\(seq===M081\.seq\)\{M081\.loading=false/);
console.log('0.8.8 channel filter/sort browser logic: 12 checks passed');

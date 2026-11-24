'use strict';
const $ = (id) => document.getElementById(id);
const S = {csrf:null, page:'overview', contacts:[], messages:[], events:[], alerts:[], history:[], jobs:[], mapNodes:[], health:null, channels:{slots:[]}, addressBook:[], rxLog:[], routing:null, routingCatalog:null, txDiag:null, radioDiag:null, status:null};
const H = (v) => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt = (v) => {const d=v?new Date(v):null;return d&&!Number.isNaN(d.getTime())?d.toLocaleString():'—'};
const short = (v,n=18) => String(v||'').length>n ? String(v).slice(0,n)+'…' : String(v||'');
function toast(s, error=false){let t=$('toast');t.textContent=s;t.className='toast show'+(error?' error':'');clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.className='toast',5000)}
async function request(path, opt={}){
  const options={credentials:'same-origin',...opt,headers:{...(opt.headers||{})}};
  if(options.body && !(options.body instanceof FormData))options.headers['Content-Type']='application/json';
  if(['POST','PUT','DELETE','PATCH'].includes(options.method))options.headers['X-CSRF-Token']=S.csrf||'';
  const res=await fetch(path,options);
  let data;try{data=await res.json()}catch{data={detail:res.statusText}}
  if(res.status===401 && path!='/api/login'){showLogin();throw Error('Session expired. Sign in again.')}
  if(!res.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
}
function grafanaLinkUrl(me, current=location){
  const configured=String(me?.grafana_url||'').trim();
  if(configured){
    try{
      const url=new URL(configured);
      if(['http:','https:'].includes(url.protocol) && url.hostname && !url.username && !url.password)
        return url.href;
    }catch{/* Invalid configuration falls back to the local port. */}
  }
  const port=Number(me?.grafana_port);
  const validPort=Number.isInteger(port) && port>=1 && port<=65535?port:3300;
  return `${current.protocol}//${current.hostname}:${validPort}/`;
}
function setGrafanaLink(me){$('grafana-link').href=grafanaLinkUrl(me)}
function showLogin(){S.csrf=null;$('shell').hidden=true;$('login-screen').hidden=false}
function showApp(){ $('login-screen').hidden=true;$('shell').hidden=false }
function navigate(view){S.page=view;document.querySelectorAll('.view').forEach(e=>e.hidden=e.id!=='view-'+view);document.querySelectorAll('[data-view]').forEach(e=>e.classList.toggle('active',e.dataset.view===view));$('page-title').textContent=({overview:'Overview',messages:'Messages',nodes:'Nodes & Contacts',alerts:'Alerts',events:'Event Log',firmware:'Firmware Manager',map:'Node Map',radio:'Radio Settings',monitor:'Radio Monitor',channels:'Channel Management',address:'Address Book',digest:'Email Digests',routing:'Routing & Regions','my-node':'My Node & Adverts'})[view];render();if(view==='map')requestAnimationFrame(()=>requestAnimationFrame(updateMap));if(view==='digest')loadDigest();if(view==='messages')reloadMessageHistory();}
function empty(text){return `<div class="empty">${H(text)}</div>`}
function nodeStyle(role){
  const roleKey=String(role||'unknown').toLowerCase().replaceAll(' ','_');
  return ({repeater:['repeater','↗','Repeater'],client:['client','●','Companion'],room_server:['room_server','▣','Room server'],sensor:['sensor','◆','Sensor'],self:['self','⌖','My station']})[roleKey]||['unknown','?','Unknown'];
}
function nodeTag(role){const [css,icon,label]=nodeStyle(role);return `<span class="node-tag ${css}"><span aria-hidden="true">${icon}</span> ${H(label)}</span>`}
function messageStatus(v){return ({sent:'Radio accepted · delivery unconfirmed',sent_unconfirmed:'Radio accepted · delivery unconfirmed',acknowledged:'Direct ACK received',simulated:'Simulated'})[v]||String(v||'')}
function txLabel(m){
 if(m.direction!=='out')return messageStatus(m.status);
 const evidence=m.tx_evidence||[];
 if(m.kind==='direct' && (m.status==='acknowledged'||evidence.some(x=>x.kind==='direct_ack')))return 'Direct ACK received';
 if(m.kind==='channel' && evidence.some(x=>x.kind==='channel_echo'))return 'Matching channel repeat heard · recipient unconfirmed';
 if(evidence.some(x=>x.kind==='radio_accepted') || m.status==='sent_unconfirmed')return 'Radio accepted · delivery unconfirmed';
 return messageStatus(m.status);
}
function renderTxDiagnostics(){
 const t=S.txDiag;if(!t)return;
 const x=$('tx-confirmation-stats');if(!x)return;
 x.innerHTML=[['Radio accepted',t.accepted],['Direct ACKs',t.direct_acknowledged],['Channel echoes',t.channel_echo_observed],['Unconfirmed',t.unconfirmed]].map(([a,b])=>`<div class="tx-stat"><span>${H(a)}</span><b>${Number(b)||0}</b></div>`).join('');

}

function messageHeading(m){const node=messageDisplaySender086(m);return `${m.kind==='channel'?'#'+m.target:'Direct'} · ${m.direction==='in'?'Received':'Sent'} · ${node}`}
function item(title,body,time,dot=''){return `<div class="stream-item"><span class="dot ${H(dot)}"></span><div class="stream-main"><div class="stream-head"><div class="stream-title">${H(title)}</div><time class="stream-time">${H(dt(time))}</time></div><div class="stream-body">${H(body)}</div></div></div>`}
function plot(element, values, key, unit){
  const target=$(element), list=values.filter(x=>typeof x[key]==='number' && Number.isFinite(x[key]));
  if(!list.length){target.innerHTML=empty('No telemetry yet');return}
  const width=700,height=210,pad=42;const n=list.length;
  let min=Math.min(...list.map(x=>x[key])),max=Math.max(...list.map(x=>x[key]));if(min===max){min-=1;max+=1}let delta=(max-min)*.13;min-=delta;max+=delta;
  const pt=list.map((x,i)=>{const px=pad+(width-pad*1.4)*(n===1?.5:i/(n-1));const py=height-pad-((x[key]-min)/(max-min))*(height-pad*1.6);return [px,py]});
  const p=pt.map(x=>x.join(',')).join(' ');
  let grid='';for(let i=0;i<4;i++){const y=18+i*46;grid+=`<line x1="${pad}" y1="${y}" x2="690" y2="${y}" stroke="#28414b" stroke-dasharray="3 5"/><text x="2" y="${y+4}" fill="#8caaba" font-size="12">${(max-(y-18)/(height-pad*1.6)*(max-min)).toFixed(0)}</text>`}
  target.innerHTML=`<svg role="img" aria-label="${H(key)} history chart" viewBox="0 0 ${width} ${height}">${grid}<polyline fill="none" stroke="#42d7bf" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" points="${p}"/><circle cx="${pt[n-1][0]}" cy="${pt[n-1][1]}" r="5" fill="#42d7bf"/><text x="690" y="205" text-anchor="end" fill="#8caaba" font-size="12">${H(new Date(list[n-1].ts).toLocaleTimeString())} · ${list[n-1][key].toFixed(1)} ${H(unit)}</text></svg>`;
}
function fillDestinations(){let old=$('destination').value;const channels=(S.status?.channels?.length?S.status.channels:Array.from({length:8},(_,i)=>({index:i,name:'Channel '+i})));$('destination').innerHTML=channels.map(c=>`<option value="channel:${c.index}">${H(c.name)} (#${c.index})</option>`).join('')+S.contacts.map(x=>`<option value="${H(x.key)}">${H(x.name)} (${H(short(x.key,12))})</option>`).join('');if([...$('destination').options].some(o=>o.value===old))$('destination').value=old}
function fillArchiveDestinations(){
 const select=$('history-destination');if(!select)return;
 const previous=select.value;
 const options=['<option value="all">All channels and DMs</option>',
                '<option value="direct">Direct messages only</option>'];
 for(let index=0;index<8;index++){
  options.push(`<option value="channel:${index}">${H(channelName086(index))} (#${index})</option>`);
 }
 // Avoid replacing the dropdown during every 10-second status refresh; doing so
 // can reset focus, the selected channel, or an open native select on mobile.
 const markup=options.join('');
 if(select.innerHTML!==markup){
  select.innerHTML=markup;
  if([...select.options].some(o=>o.value===previous))select.value=previous;
 }
}
function render(){if(!$('shell') || $('shell').hidden || !S.status)return;
 const st=S.status, radio=st.radio||{};$('mode-badge').textContent='USB SERIAL';$('mode-badge').className='pill';$('connection-badge').textContent=radio.connected?'● Connected':'● Offline';$('connection-badge').className='pill '+(radio.connected?'':'red');$('kpi-radio').textContent=radio.connected?'Online':'Offline';$('kpi-device').textContent=radio.error||radio.device||'Awaiting device';$('kpi-nodes').textContent=st.counts.contacts;const sync=st.contact_sync||{};const syncText=typeof sync.radio_contacts==='number'?`${sync.radio_contacts} on radio · +${sync.new_in_sync||0} new at last sync`:'Awaiting radio contact sync';$('nodes-kpi-detail').textContent=syncText;$('contact-sync-summary').textContent=`${syncText}${sync.sync_at?' · '+dt(sync.sync_at):''}. RX packets do not increase this count automatically.`;$('kpi-messages').textContent=st.counts.messages;$('power-title').textContent=st.power_source==='usb'?'POWER SOURCE':'BATTERY';$('kpi-battery').textContent=st.power_source==='usb'?'USB Powered':(st.sample?.battery_pct!=null ? st.sample.battery_pct.toFixed(0)+'%' : '—');$('kpi-battery').style.fontSize=st.power_source==='usb'?'1.35rem':'';$('power-caption').textContent=st.power_source==='usb'?'No battery installed':'Most recent telemetry';$('battery-panel').hidden=st.power_source==='usb';
 const rec=S.messages.slice(0,7);$('recent-messages').innerHTML=rec.length?rec.map(m=>item(messageHeading(m),m.text,m.ts,m.direction)).join(''):empty('No messages yet');
 $('recent-nodes').innerHTML=S.contacts.length?S.contacts.slice(0,6).map(n=>`<div class="node-row">${nodeTag(n.role)}${item(n.name,short(n.key,36),n.last_seen)}</div>`).join(''):empty('No contacts discovered');
 $('contacts-table').innerHTML=S.contacts.length?S.contacts.map(n=>`<tr><td>${H(n.name)}</td><td>${nodeTag(n.role)}</td><td><code title="${H(n.key)}">${H(short(n.key,40))}</code></td><td>${H(dt(n.last_seen))}</td><td><button class="subtle" type="button" data-save-contact="${H(n.key)}">Save ↗</button></td></tr>`).join(''):`<tr><td colspan="5">No contacts discovered yet</td></tr>`;
 $('recent-alerts').innerHTML=S.alerts.filter(a=>!a.resolved).length?S.alerts.filter(a=>!a.resolved).slice(0,5).map(a=>item(a.severity.toUpperCase(),a.message,a.ts,'danger')).join(''):empty('No active alerts');
 $('all-alerts').innerHTML=S.alerts.length?S.alerts.map(a=>`<div class="stream-item"><span class="dot ${a.resolved?'':'danger'}"></span><div class="stream-main"><div class="stream-head"><b>${H(a.severity.toUpperCase())}</b><span class="stream-time">${H(dt(a.ts))}</span></div><p class="stream-body">${H(a.message)}</p></div>${a.resolved?'<span class="pill">Resolved</span>':`<button class="button secondary" data-resolve="${a.id}">Resolve</button>`}</div>`).join(''):empty('No alerts');
 $('event-list').innerHTML=S.events.length?S.events.map(e=>item(e.kind,JSON.stringify(e.detail),e.ts)).join(''):empty('No radio events');
 $('telemetry-info').textContent=JSON.stringify({radio,latest:st.sample,known_contacts:st.counts.contacts,logged_messages:st.counts.messages,raw_radio_stats:st.last_stats},null,2);
 plot('overview-chart',S.history,'noise','dBm');if(st.power_source!=='usb')plot('battery-chart',S.history,'battery','%');
 $('firmware-jobs').innerHTML=S.jobs.length?S.jobs.map(j=>`<div class="stream-item"><span class="dot ${['failed','error'].includes(j.status)?'danger':j.status==='complete'?'':'warn'}"></span><div class="stream-main"><div class="stream-title">${H(j.filename||j.id)}</div><div class="stream-body">${H(j.status)} · ${H(j.message||'')}</div></div><button class="subtle" data-job="${H(j.id)}">Logs</button></div>`).join(''):empty('No firmware updates yet');
 $('radio-channel-list').textContent=(st.channels||[]).map(c=>`${c.index}: ${c.name||'(empty)'}`).join(' · ')||'No channel information';$('last-refresh').textContent='Refreshed '+new Date().toLocaleTimeString();fillDestinations();fillArchiveDestinations();
}
let loading=false;
async function refresh(){if(!S.csrf || loading)return;loading=true;try{
  const [st,contacts,msg,events,alerts,hist,jobs,mapNodes,health,channels,addressBook,rxLog,txDiag]=await Promise.all([request('/api/status'),request('/api/contacts'),request('/api/messages?limit=300'),request('/api/events?limit=100'),request('/api/alerts'),request('/api/history?hours=24'),request('/api/firmware/jobs'),request('/api/map/nodes'),request('/api/radio/health'),request('/api/channels'),request('/api/address-book'),request('/api/radio/rx-log?limit=150'),request('/api/tx/diagnostics')]);
  Object.assign(S,{status:st,contacts,messages:msg,events,alerts,history:hist,jobs,mapNodes,health,channels,addressBook,rxLog,txDiag});render();renderTxDiagnostics();renderHealth();renderChannels();renderAddressBook();renderRxLog();if(S.page==='map')updateMap();
}catch(e){toast(e.message,true)}finally{loading=false}}
async function enqueue(payload){const x=await request('/api/commands',{method:'POST',body:JSON.stringify(payload)});toast('Command queued #'+x.id);const deadline=Date.now()+20000;while(Date.now()<deadline){await new Promise(r=>setTimeout(r,1200));let y=await request('/api/commands/'+x.id);if(y.state==='failed')throw Error(y.error);if(y.state==='complete'){toast('Radio command accepted');await refresh();return y}}
 toast('Command queued. Check activity for results.')}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';const form=new FormData(e.target);try{const res=await request('/api/login',{method:'POST',body:JSON.stringify({username:form.get('username'),password:form.get('password')})});S.csrf=res.csrf;showApp();const me=await request('/api/me');setGrafanaLink(me);await refresh()}catch(err){$('login-error').textContent=err.message}});
document.querySelectorAll('[data-view]').forEach(e=>e.addEventListener('click',()=>navigate(e.dataset.view)));
document.querySelectorAll('.go-messages').forEach(e=>e.addEventListener('click',()=>navigate('messages')));
$('logout').addEventListener('click',async()=>{try{await request('/api/logout',{method:'POST'})}finally{showLogin()}});
$('logout-mobile').addEventListener('click',()=>{$('logout').click()});
$('refresh').addEventListener('click',refresh);
$('message-text').addEventListener('input',()=>{$('char-count').textContent=$('message-text').value.length+' / 180'});
$('send-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await enqueue({kind:'send',destination:$('destination').value,text:$('message-text').value});$('message-text').value='';$('char-count').textContent='0 / 180';$('reply-context').hidden=true}catch(err){toast(err.message,true)}finally{b.disabled=false}});
for(const id of ['sync-contacts','overview-discover'])$(id).addEventListener('click',async()=>{try{await enqueue({kind:'contacts'})}catch(e){toast(e.message,true)}});
$('advertise').addEventListener('click',()=>navigate('my-node'));
$('all-alerts').addEventListener('click',async e=>{let id=e.target.dataset.resolve;if(!id)return;try{await request('/api/alerts/'+id+'/resolve',{method:'POST'});await refresh()}catch(err){toast(err.message,true)}});
$('firmware-form').addEventListener('submit',async e=>{e.preventDefault();if(!confirm('This will stop the collector and flash the T114. Continue?'))return;let btn=e.submitter;btn.disabled=true;try{const f=new FormData();f.append('file',$('firmware-file').files[0]);f.append('confirmation',$('flash-confirm').value);let job=await request('/api/firmware/upload',{method:'POST',body:f});toast('Firmware job queued: '+job.id);$('firmware-form').reset();await refresh();await showJob(job.id)}catch(err){toast(err.message,true)}finally{btn.disabled=false}});
async function showJob(id){try{let j=await request('/api/firmware/jobs/'+id);$('firmware-log').textContent=`${j.status}: ${j.message||''}\nSHA256: ${j.sha256||''}\n\n${j.log||'No flashing output yet.'}`}catch(e){toast(e.message,true)}}
$('firmware-jobs').addEventListener('click',e=>{const id=e.target.dataset.job;if(id)showJob(id)});
$('export-messages').addEventListener('click',async e=>{e.preventDefault();try{const res=await fetch('/api/export/messages.csv',{credentials:'same-origin'});if(!res.ok)throw Error('Export failed');const blob=await res.blob();let u=URL.createObjectURL(blob);let a=document.createElement('a');a.href=u;a.download='meshcore-messages.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),3000)}catch(err){toast(err.message,true)}});
(async()=>{try{let me=await request('/api/me');S.csrf=me.csrf;showApp();setGrafanaLink(me);await refresh()}catch{showLogin()}})();
setInterval(()=>{if(S.csrf)refresh()},10000);

// Dependency-free, Firefox-safe map. No hidden-tab Leaflet initialisation, no CDN scripts.
// Tiles are decorative. Nodes and geographic grid render even when tiles are blocked.
const mapState={center:[47.6588,-117.4260],zoom:10,userMoved:false,lastSignature:'',drag:null,initialized:false};
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
function geoWorld(lat,lon,z){const size=256*2**z, y=clamp(lat,-85.0511,85.0511)*Math.PI/180;
 return {x:(lon+180)/360*size,y:(1-Math.log(Math.tan(y)+1/Math.cos(y))/Math.PI)/2*size}}
function geoInverse(x,y,z){const size=256*2**z,worldLon=x/size*360-180, n=Math.PI-2*Math.PI*y/size;
 return [180/Math.PI*Math.atan(Math.sinh(n)), ((worldLon+540)%360)-180]}
function mapFit(){const nodes=(S.mapNodes||[]).filter(n=>n.location&&Number.isFinite(n.location.lat)&&Number.isFinite(n.location.lon));
 const box=$('map-canvas'),w=box.clientWidth,h=box.clientHeight;
 if(!nodes.length||!w||!h){mapState.center=[47.6588,-117.4260];mapState.zoom=10;return}
 const minlat=Math.min(...nodes.map(n=>n.location.lat)),maxlat=Math.max(...nodes.map(n=>n.location.lat));
 const minlon=Math.min(...nodes.map(n=>n.location.lon)),maxlon=Math.max(...nodes.map(n=>n.location.lon));
 mapState.center=[(minlat+maxlat)/2,(minlon+maxlon)/2];let z=14;
 for(;z>3;z--){const nw=geoWorld(maxlat,minlon,z),se=geoWorld(minlat,maxlon,z);
 if(Math.abs(se.x-nw.x)<Math.max(50,w-110)&&Math.abs(se.y-nw.y)<Math.max(50,h-110))break}
 mapState.zoom=clamp(z,3,14)}
function mapPaint(force=false){const el=$('map-canvas');if(S.page!=='map'||!el||el.clientWidth<50||el.clientHeight<50)return;
 const w=el.clientWidth,h=el.clientHeight,z=mapState.zoom,center=geoWorld(...mapState.center,z);
 const nodes=(S.mapNodes||[]).filter(n=>n.location&&Number.isFinite(n.location.lat)&&Number.isFinite(n.location.lon));
 const signature=JSON.stringify([w,h,z,...mapState.center,nodes.map(n=>[n.key,n.name,n.role,n.location.lat,n.location.lon])]);
 if(!force && signature===mapState.lastSignature)return;
 mapState.lastSignature=signature;
 const tileStartX=Math.floor((center.x-w/2)/256),tileEndX=Math.floor((center.x+w/2)/256);
 const tileStartY=Math.floor((center.y-h/2)/256),tileEndY=Math.floor((center.y+h/2)/256);const maxTile=2**z;
 const grid=document.createElement('div');grid.className='map-tile-grid';let tileTotal=0,tileFailed=0;
 for(let tx=tileStartX;tx<=tileEndX;tx++)for(let ty=tileStartY;ty<=tileEndY;ty++){
  if(ty<0||ty>=maxTile)continue;
  const im=document.createElement('img');im.alt='';im.decoding='async';im.draggable=false;im.className='map-tile';
  im.style.left=Math.round(tx*256-center.x+w/2)+'px';im.style.top=Math.round(ty*256-center.y+h/2)+'px';
  im.src=`https://tile.openstreetmap.org/${z}/${(tx+maxTile)%maxTile}/${ty}.png`;tileTotal++;
  im.onerror=()=>{tileFailed++;if(tileFailed===tileTotal)$('map-fallback').hidden=false};grid.appendChild(im)
 }
 $('map-tiles').replaceChildren(grid);$('map-fallback').hidden=true;
 const pins=document.createDocumentFragment();
 for(const n of nodes){const coords=geoWorld(n.location.lat,n.location.lon,z),px=coords.x-center.x+w/2,py=coords.y-center.y+h/2;
  if(px<-50||px>w+50||py<-50||py>h+50)continue;
  const [roleClass,roleIcon]=nodeStyle(n.role);const b=document.createElement('button');b.className='map-pin '+roleClass;b.type='button';
  b.style.left=px+'px';b.style.top=py+'px';
  b.textContent=roleIcon;b.title=`${n.name} (${n.role}) · ${n.location.source} location`;
  b.setAttribute('aria-label',b.title);b.addEventListener('click',e=>{e.stopPropagation();toast(b.title)});pins.appendChild(b)
 }
 $('map-pins').replaceChildren(pins);
}
function updateMap(){
 const nodes=S.mapNodes||[],positioned=nodes.filter(n=>n.location),unmapped=nodes.filter(n=>!n.location);
 $('map-summary').textContent=`${positioned.length} plotted · ${unmapped.length} without coordinates · ${nodes.filter(n=>n.role==='repeater').length} repeaters in radio contacts. RX packet counts are not node counts.`;
 $('map-unmapped').innerHTML=unmapped.length?unmapped.map(n=>`<div class="node-row">${nodeTag(n.role)}${item(n.name,'Coordinates not advertised',n.last_seen)}</div>`).join(''):empty('No unmapped contacts.');
 const el=$('map-contact'),prior=el.value;
 const selections=nodes.map(n=>`<option value="${H(n.key)}">${H(n.name)} (${H(n.role)})</option>`).join('');
 if(el.innerHTML!==selections){el.innerHTML=selections;if(nodes.some(n=>n.key===prior))el.value=prior}
 if(!mapState.initialized){mapFit();mapState.initialized=true}
 requestAnimationFrame(()=>mapPaint())
}
function moveMapBy(dx,dy){const z=mapState.zoom,c=geoWorld(...mapState.center,z);
 mapState.center=geoInverse(c.x-dx,c.y-dy,z);mapState.userMoved=true;mapPaint(true)}
const mapCanvas=$('map-canvas');
mapCanvas.addEventListener('pointerdown',e=>{if(e.target.closest('button'))return;mapState.drag={x:e.clientX,y:e.clientY};mapCanvas.setPointerCapture(e.pointerId)});
mapCanvas.addEventListener('pointerup',e=>{if(mapState.drag){moveMapBy(e.clientX-mapState.drag.x,e.clientY-mapState.drag.y);mapState.drag=null}});
mapCanvas.addEventListener('pointercancel',()=>mapState.drag=null);
mapCanvas.addEventListener('wheel',e=>{e.preventDefault();mapState.zoom=clamp(mapState.zoom+(e.deltaY<0?1:-1),3,15);mapPaint(true)},{passive:false});
$('map-zoom-in').addEventListener('click',()=>{mapState.zoom=clamp(mapState.zoom+1,3,15);mapPaint(true)});
$('map-zoom-out').addEventListener('click',()=>{mapState.zoom=clamp(mapState.zoom-1,3,15);mapPaint(true)});
$('map-fit').addEventListener('click',()=>{mapFit();mapPaint(true)});
if(typeof ResizeObserver!=='undefined'){new ResizeObserver(()=>{if(S.page==='map')mapPaint(true)}).observe(mapCanvas)}
window.addEventListener('resize',()=>{if(S.page==='map')mapPaint(true)});
$('map-refresh').addEventListener('click',async()=>{try{await refresh()}catch(e){toast(e.message,true)}});
$('manual-location-form').addEventListener('submit',async e=>{e.preventDefault();const k=$('map-contact').value;if(!k)return;try{await request('/api/map/nodes/'+encodeURIComponent(k)+'/location',{method:'PUT',body:JSON.stringify({latitude:Number($('map-lat').value),longitude:Number($('map-lon').value)})});toast('Manual location saved');await refresh()}catch(err){toast(err.message,true)}});
$('map-clear').addEventListener('click',async()=>{const k=$('map-contact').value;if(!k)return;try{await request('/api/map/nodes/'+encodeURIComponent(k)+'/location',{method:'DELETE'});toast('Manual location cleared');await refresh()}catch(err){toast(err.message,true)}});
async function pollCommand(id){const timeout=Date.now()+20000;while(Date.now()<timeout){await new Promise(r=>setTimeout(r,1100));const x=await request('/api/commands/'+id);if(x.state==='failed')throw Error(x.error);if(x.state==='complete')return x.result;}throw Error('Radio still processing. Check later.');}
$('radio-read').addEventListener('click',async()=>{try{const x=await request('/api/radio/read',{method:'POST'});const result=await pollCommand(x.id);$('radio-current').textContent=JSON.stringify(result,null,2);if(result.name)$('radio-name').value=result.name;await refresh()}catch(e){toast(e.message,true)}});
$('radio-settings-form').addEventListener('submit',async e=>{e.preventDefault();const update={confirm:$('radio-confirm').value};const name=$('radio-name').value.trim(),power=$('radio-power').value,preset=$('radio-preset').value;if(name)update.name=name;if(power)update.tx_power=Number(power);if(preset==='us')Object.assign(update,{radio_freq:910.525,radio_bw:62.5,radio_sf:7,radio_cr:5});if(!confirm('Apply settings to the actual T114? Incorrect RF settings can disconnect it from the mesh.'))return;try{const x=await request('/api/radio/settings',{method:'POST',body:JSON.stringify(update)});const result=await pollCommand(x.id);toast('Radio settings accepted');$('radio-current').textContent=JSON.stringify(result,null,2);await refresh()}catch(err){toast(err.message,true)}});

// Hardware radio health: no inferred battery percentage or fabricated RX progress.
function renderHealth(){const h=S.health;if(!h)return;
 const d=h.measurements||{};const show=v=>typeof v==='number'?Number(v).toLocaleString():'—';
 $('monitor-connection').textContent=h.connected?'Online':'Offline';
 $('health-rx').textContent=show(d.rx);$('health-tx').textContent=show(d.tx);$('health-errors').textContent=show(d.rx_errors);
 $('monitor-signal-details').innerHTML=[['Last RSSI',d.rssi==null?'Unavailable':show(d.rssi)+' dBm'],['Noise floor',d.noise_floor==null?'Unavailable':show(d.noise_floor)+' dBm'],['SNR',d.snr==null?'Unavailable':show(d.snr)+' dB']].map(([k,v])=>`<div class="health-detail"><span>${H(k)}</span><b>${H(v)}</b></div>`).join('');
 $('health-age').textContent=typeof h.sample_age_secs==='number'?`${h.sample_age_secs}s`:'—';
 $('health-freshness').textContent=h.sample_fresh?'Recent telemetry':'Telemetry delayed/stale';
 $('health-details').innerHTML=[['Flood RX',show(d.flood_rx)],['Direct RX',show(d.direct_rx)],['Flood TX',show(d.flood_tx)],['Direct TX',show(d.direct_tx)],['RX airtime',d.rx_air_secs==null?'Unavailable':show(d.rx_air_secs)+' s'],['TX airtime',d.tx_air_secs==null?'Unavailable':show(d.tx_air_secs)+' s']].map(([k,v])=>`<div class="health-detail"><span>${H(k)}</span><b>${H(v)}</b></div>`).join('');
}
function updateChannelSaveHint(){
 const slot=Number($('channel-slot').value);
 const configured=(S.channels?.slots||[]).find(c=>Number(c.index)===slot)?.configured;
 $('channel-save-hint').textContent=configured
   ? 'Leave the key blank to keep the existing shared key; entering one replaces it.'
   : 'For a public hashtag channel (#name), leave the key blank to derive it automatically. Private groups require an existing shared key.';
}
function channelSaveStatus(message, failed=false){
 const el=$('channel-save-status');el.textContent=message;
 el.style.color=failed?'#ed8991':'';
}
function renderChannels(){const slots=S.channels?.slots||[];
 $('channels-table').innerHTML=slots.map(c=>`<tr><td>#${c.index}</td><td>${H(c.name||'—')}</td><td>${c.configured?'Configured':'Empty'}</td><td><button class="subtle" type="button" data-edit-channel="${c.index}">Edit</button></td></tr>`).join('');
 const opts=slots.map(c=>`<option value="${c.index}">#${c.index} · ${H(c.name||'(empty)')}</option>`).join('');
 for(const id of ['channel-slot','channel-delete-slot']){const e=$(id),old=e.value;if(e.innerHTML!==opts){e.innerHTML=opts;if(slots.some(c=>String(c.index)===old))e.value=old}}
 updateChannelSaveHint();
}
$('channels-table').addEventListener('click',e=>{const idx=e.target.dataset.editChannel;if(idx===undefined)return;
 $('channel-slot').value=idx;$('channel-name').value=S.channels.slots.find(c=>String(c.index)===idx)?.name||'';$('channel-key').value='';channelSaveStatus('');updateChannelSaveHint();$('channel-name').focus()});
$('channel-slot').addEventListener('change',()=>{channelSaveStatus('');$('channel-key').value='';updateChannelSaveHint()});
$('channel-delete-slot').addEventListener('change',e=>{$('channel-delete-confirm').placeholder='DELETE CHANNEL '+e.target.value});
$('channel-form').addEventListener('submit',async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;
 try{
  const idx=Number($('channel-slot').value),name=$('channel-name').value.trim(),secret=$('channel-key').value.trim();
  const configured=(S.channels?.slots||[]).find(c=>Number(c.index)===idx)?.configured;
  if(!name)throw Error('Enter a channel name.');
  if(secret && !/^[0-9a-fA-F]{32}$/.test(secret))throw Error('Shared key must be 32 hexadecimal characters.');
  if(!configured && !secret && !name.startsWith('#'))throw Error('For a new private channel, enter its shared key. Hashtag channels (#name) derive their key automatically.');
  channelSaveStatus('Saving channel to T114…');
  const x=await request('/api/channels/'+idx,{method:'PUT',body:JSON.stringify({name,secret_hex:secret||null})});
  await pollCommand(x.id);
  $('channel-key').value='';
  await refresh();
  channelSaveStatus('Channel saved to radio.');
  toast('Channel saved to radio');
 }catch(err){channelSaveStatus(err.message,true);toast(err.message,true)}finally{btn.disabled=false}});
$('channel-delete-form').addEventListener('submit',async e=>{e.preventDefault();const idx=Number($('channel-delete-slot').value);
 if(!confirm(`Permanently erase channel ${idx} from the T114? Its shared key will be lost.`))return;
 const btn=e.submitter;btn.disabled=true;
 try{const x=await request('/api/channels/'+idx,{method:'DELETE',body:JSON.stringify({confirm:$('channel-delete-confirm').value})});await pollCommand(x.id);$('channel-delete-confirm').value='';toast('Channel deleted');await refresh()}
 catch(err){toast(err.message,true)}finally{btn.disabled=false}});
$('channels-refresh').addEventListener('click',async()=>{try{const x=await request('/api/channels/refresh',{method:'POST'});await pollCommand(x.id);await refresh();toast('Channel slots refreshed from T114')}catch(err){toast(err.message,true)}});

// Local address book: this does not modify the radio's own contact list.
function resetAddress(){
 $('address-form').reset();$('address-id').value='';$('address-delete').hidden=true;
 $('address-message').hidden=true;$('address-form-heading').textContent='Save contact';
}
function fillAddress(a){
 $('address-id').value=a.id;$('address-name').value=a.nickname;
 $('address-key').value=a.public_key||'';$('address-tags').value=a.tags||'';
 $('address-notes').value=a.notes||'';$('address-favorite').checked=!!a.favorite;
 $('address-delete').hidden=false;
 $('address-message').hidden=!(a.public_key && S.contacts.some(x=>x.key===a.public_key));
 $('address-form-heading').textContent='Edit saved contact';
}
function renderAddressBook(){
 const q=($('address-search').value||'').trim().toLowerCase();
 const filtered=(S.addressBook||[]).filter(a=>
  [a.nickname,a.public_key,a.notes,a.tags,a.radio_name].some(x=>String(x||'').toLowerCase().includes(q)));
 $('address-entries').innerHTML=filtered.length?filtered.map(a=>`<button class="address-entry" type="button" data-address-id="${a.id}"><span><strong>${H(a.nickname)}</strong> ${nodeTag(a.role)}<span class="secondary">${H(a.tags||'No tags')} · ${a.radio_contact?'On T114':'Saved locally'} · ${H(short(a.public_key||'No public key',23))}</span></span><span class="star" aria-label="${a.favorite?'Favorite':'Not favorite'}">${a.favorite?'★':'☆'}</span></button>`).join(''):empty(q?'No matching entries.':'No saved contacts yet. Select a discovered contact or add one manually.');
}
$('address-search').addEventListener('input',renderAddressBook);
$('address-reset').addEventListener('click',resetAddress);
$('address-entries').addEventListener('click',e=>{let b=e.target.closest('[data-address-id]');if(!b)return;let a=S.addressBook.find(x=>x.id===Number(b.dataset.addressId));if(a)fillAddress(a)});
$('address-form').addEventListener('submit',async e=>{
 e.preventDefault();let id=$('address-id').value;const body={nickname:$('address-name').value.trim(),public_key:$('address-key').value.trim()||null,
 notes:$('address-notes').value,tags:$('address-tags').value,favorite:$('address-favorite').checked};
 try{await request(id?'/api/address-book/'+id:'/api/address-book',{method:id?'PUT':'POST',body:JSON.stringify(body)});resetAddress();await refresh();toast('Address book saved')}
 catch(err){toast(err.message,true)}
});
$('address-delete').addEventListener('click',async()=>{
 const id=$('address-id').value;if(!id||!confirm('Delete this address book entry? This does not remove radio contacts.'))return;
 try{await request('/api/address-book/'+id,{method:'DELETE'});resetAddress();await refresh();toast('Address removed')}catch(err){toast(err.message,true)}
});
$('address-message').addEventListener('click',()=>{
 const key=$('address-key').value.trim().toLowerCase();
 if(!S.contacts.some(x=>x.key===key)){toast('Sync this contact to the T114 before direct messaging',true);return}
 navigate('messages');$('destination').value=key;$('message-text').focus();
});
function renderRxLog(){
 const filter=$('rx-filter').value;
 const rows=(S.rxLog||[]).filter(x=>!filter||x.kind===filter);
 $('health-rx-log').innerHTML=rows.length?rows.map(r=>{
  const signals=[Number.isFinite(r.rssi)?`${r.rssi} dBm`:'',Number.isFinite(r.snr)?`${r.snr} dB SNR`:''].filter(Boolean).join(' · ')||'—';
  const more=r.kind==='counter_delta'?`+${r.count} received, +${r.errors} errors · aggregate only`:
    [r.channel===null?'':`Channel ${r.channel}`,r.source?short(r.source,18):''].filter(Boolean).join(' · ');
  return `<div class="rx-line"><time>${H(dt(r.ts))}</time><div><span class="rx-kind">${H(r.summary)}</span><span class="rx-extra">${H(more)}</span></div><span class="rx-values">${H(signals)}</span></div>`
 }).join(''):empty('No receive events in this filter yet.');
}
$('rx-filter').addEventListener('change',renderRxLog);
$('contacts-table').addEventListener('click',async e=>{
 const button=e.target.closest('[data-save-contact]');if(!button)return;
 const found=S.contacts.find(c=>c.key===button.dataset.saveContact);if(!found)return;
 const existing=S.addressBook.find(x=>x.public_key===found.key);
 if(existing){fillAddress(existing);navigate('address');return}
 resetAddress();$('address-name').value=found.name;$('address-key').value=found.key;navigate('address');
});

// v5: SMTP digest settings are independent of the radio serial connection.
let digestSettingsLoaded=false;
function digestFormData(){
  const data={enabled:$('digest-enabled').checked,frequency:$('digest-frequency').value,
    send_time:$('digest-time').value,weekday:Number($('digest-weekday').value),
    timezone:$('digest-timezone').value.trim(),
    smtp_host:$('digest-host').value.trim(),smtp_port:Number($('digest-port').value),
    smtp_security:$('digest-security').value,smtp_username:$('digest-username').value.trim(),
    smtp_password:$('digest-password').value||null,clear_password:$('digest-clear-password').checked,
    mail_from:$('digest-from').value.trim(),mail_to:$('digest-recipients').value.trim(),
    message_limit:Number($('digest-limit').value)};
  for(const sec of ['received','sent','radio','alerts','nodes','rx'])data['include_'+sec]=$('digest-section-'+sec).checked;
  return data;
}
async function loadDigest(){
  try{
    const x=await request('/api/digest/settings');digestSettingsLoaded=true;
    for(const [field,id] of Object.entries({enabled:'digest-enabled',frequency:'digest-frequency',
      send_time:'digest-time',weekday:'digest-weekday',timezone:'digest-timezone',
      smtp_host:'digest-host',smtp_port:'digest-port',smtp_security:'digest-security',
      smtp_username:'digest-username',mail_from:'digest-from',mail_to:'digest-recipients',
      message_limit:'digest-limit'})){
      if($(id).type==='checkbox')$(id).checked=!!x[field];else $(id).value=x[field]??'';
    }
    for(const sec of ['received','sent','radio','alerts','nodes','rx'])$('digest-section-'+sec).checked=!!x['include_'+sec];
    $('digest-password').value='';$('digest-clear-password').checked=false;
    $('digest-password-state').textContent=x.password_configured?'An SMTP password is saved (encrypted). Leave blank to retain it.':'No SMTP password saved.';
    $('digest-worker-status').textContent=x.worker_online?'● Scheduler online':'● Scheduler offline — queued email cannot send';
    $('digest-worker-status').className='pill '+(x.worker_online?'':'red');
    $('digest-next').textContent=x.enabled?(x.next_due?'Next scheduled delivery: '+dt(x.next_due):'Next delivery not yet calculated'):'Scheduled digests disabled';
    await refreshDigestHistory();
  }catch(e){toast('Could not load digest settings: '+e.message,true)}
}
async function refreshDigestHistory(){
  if(S.page!=='digest')return;
  try{
    const rows=await request('/api/digest/history');
    $('digest-history').innerHTML=rows.length?rows.map(r=>`<tr><td>${H(dt(r.created_at))}</td><td>${H(r.kind)}</td><td>${H(r.status)}</td><td>${H(r.error||((r.status==='sent')?`${r.recipient_count} recipients · ${r.message_count} messages`:'—'))}</td></tr>`).join(''):'<tr><td colspan="4">No deliveries yet</td></tr>';
  }catch(e){toast(e.message,true)}
}
$('digest-settings-form').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;
  try{
    const res=await request('/api/digest/settings',{method:'PUT',body:JSON.stringify(digestFormData())});
    toast('Digest settings saved');await loadDigest();
  }catch(e){toast(e.message,true)}finally{button.disabled=false}
});
$('digest-preview-btn').addEventListener('click',async()=>{
  try{const res=await request('/api/digest/preview');$('digest-preview').textContent=res.text;toast('Report preview refreshed')}
  catch(e){toast(e.message,true)}
});
$('digest-refresh-btn').addEventListener('click',refreshDigestHistory);
$('digest-probe-btn').addEventListener('click',async()=>{
  try{const res=await request('/api/digest/probe-smtp',{method:'POST'});
    toast('SMTP diagnostic queued (#'+res.id+'). Check delivery history for the result.');
    await refreshDigestHistory();
  }catch(e){toast(e.message,true)}
});
$('digest-test-btn').addEventListener('click',async()=>{
  if(!confirm('Send an SMTP connectivity test to your saved recipients?'))return;
  try{const res=await request('/api/digest/send-test',{method:'POST'});toast('Test email queued (#'+res.id+'). Check delivery history.');await refreshDigestHistory()}
  catch(e){toast(e.message,true)}
});
$('digest-now-btn').addEventListener('click',async()=>{
  if(!confirm('Send a report that may include private MeshCore messages to all configured recipients?'))return;
  try{const res=await request('/api/digest/send-now',{method:'POST'});toast('Digest queued (#'+res.id+'). Check delivery history.');await refreshDigestHistory()}
  catch(e){toast(e.message,true)}
});
setInterval(()=>{if(S.csrf&&S.page==='digest')refreshDigestHistory()},15000);

// v6 Companion routing — code list editing remains local until Apply is pressed.
let routingCatalog=[];
function routeOpt(value, label, current){return `<option value="${H(value)}" ${current===value?'selected':''}>${H(label)}</option>`}
function renderRouting(){
 const r=S.routing||{};
 const names=routingCatalog;
 $('routing-current-hash').textContent=r.path_hash_bytes?`Last read: ${r.path_hash_bytes} byte(s) per hop${r.path_hash_checked_at?' · '+dt(r.path_hash_checked_at):''}`:'Hardware mode has not been read yet';
 $('routing-scope-current').textContent=r.scope_configured?`Station-managed default: ${r.default_scope||'Unscoped'} (not independently read back from radio)`:'No Station-managed default; current firmware scope is unknown';
 const choices=names.map(name=>routeOpt(name,name,r.default_scope||'')).join('');
 $('routing-default').innerHTML=routeOpt('','Unscoped — no region restriction',r.default_scope||'')+choices;
 $('routing-region-list').innerHTML=names.length?names.map(name=>`<span class="routing-chip">${H(name)} <button type="button" data-remove-region="${H(name)}" aria-label="Remove ${H(name)}">×</button></span>`).join(''):empty('No saved region codes');
 const saved=r.channel_scopes||{};
 $('routing-channel-list').innerHTML=Array.from({length:8},(_,idx)=>{
   const key=String(idx), selected=Object.hasOwn(saved,key)?saved[key]:'inherit';
   const displayName=(S.channels?.slots||[]).find(c=>Number(c.index)===idx)?.name||`Channel ${idx}`;
   return `<label class="routing-channel"><span>${H(displayName)} · #${idx}</span><select data-route-channel="${idx}">${routeOpt('inherit','Inherit default',selected)}${routeOpt('','Force unscoped',selected)}${names.map(n=>routeOpt(n,n,selected)).join('')}</select></label>`;
 }).join('');
}
async function refreshRouting(){S.routing=await request('/api/routing');routingCatalog=[...(S.routing.catalog||[])];renderRouting()}
$('routing-region-button').addEventListener('click',()=>{
 const value=$('routing-region-add').value.trim();
 if(!/^#[A-Za-z0-9][A-Za-z0-9_.-]{0,29}$/.test(value)){toast('Use a region like #Spokane (ASCII, up to 30 characters after #)',true);return}
 if(routingCatalog.includes(value)){toast('That region is already saved',true);return}
 if(routingCatalog.length>=32){toast('Maximum 32 saved region codes',true);return}
 const selectedDefault=$('routing-default').value;
 const previous=Object.fromEntries([...document.querySelectorAll('[data-route-channel]')].map(x=>[x.dataset.routeChannel,x.value]));
 routingCatalog.push(value);renderRouting();$('routing-default').value=selectedDefault;
 for(const [key,val] of Object.entries(previous)){document.querySelector(`[data-route-channel="${key}"]`).value=val}
 $('routing-region-add').value='';
});
$('routing-region-list').addEventListener('click',e=>{
 const n=e.target.dataset.removeRegion;if(!n)return;
 if(!confirm(`Remove ${n} from the local list? Any matching overrides will be reset.`))return;
 routingCatalog=routingCatalog.filter(x=>x!==n);
 renderRouting();
});
$('routing-read').addEventListener('click',async()=>{
 try{const x=await request('/api/routing/read',{method:'POST'});await pollCommand(x.id);await refreshRouting();toast('Read hardware path-hash mode')}
 catch(e){toast(e.message,true)}
});
$('routing-save').addEventListener('click',async()=>{
 const selected=$('routing-hash').value,applyScope=$('routing-apply-default').checked;
 const overrides=Object.fromEntries([...document.querySelectorAll('[data-route-channel]')].filter(x=>x.value!=='inherit').map(x=>[x.dataset.routeChannel,x.value]));
 const body={confirm:$('routing-confirm').value,catalog:routingCatalog,channel_scopes:overrides,apply_scope:applyScope};
 if(selected)body.path_hash_bytes=Number(selected);
 if(applyScope)body.default_scope=$('routing-default').value;
 if(body.confirm!=='APPLY ROUTING'){toast('Type APPLY ROUTING to confirm',true);return}
 if(!confirm('Apply routing to the live T114? Region scope can restrict which repeaters forward your messages.'))return;
 try{
  const x=await request('/api/routing',{method:'PUT',body:JSON.stringify(body)});
  const result=await pollCommand(x.id);
  $('routing-result').textContent=JSON.stringify(result,null,2);
  $('routing-confirm').value='';$('routing-hash').value='';$('routing-apply-default').checked=false;
  await refreshRouting();toast('Routing update accepted');
 }catch(e){toast(e.message,true)}
});
// Render after sign-in and on Routing navigation; do not touch the serial interface.
const oldNavigate=navigate;
navigate=function(view){oldNavigate(view);if(view==='routing')refreshRouting().catch(e=>toast(e.message,true))};

// 0.8.0 — read-only radio diagnostic timeline. Never turn an RF counter into a delivery claim.
const D08={data:null};
function diagNumber(x){return x==null?'—':Number(x).toLocaleString()}
function diagKpi(title,value,subtitle){return `<article class="kpi"><span class="eyebrow">${H(title)}</span><b>${H(value)}</b><small>${H(subtitle)}</small></article>`}
function diagDetail(name,value){return `<div class="health-detail"><span>${H(name)}</span><b>${H(value)}</b></div>`}
function renderRadioDiagnostics(){
 const d=D08.data;if(!d)return;
 const route=d.routing||{},policy=route.managed_policy||{};
 $('diag-settings').innerHTML=[
  ['TX power',d.radio_config?.tx_power==null?'Unknown':`${d.radio_config.tx_power} dBm`],
  ['Path hash',route.observed?.path_hash_bytes==null?'Not read':`${route.observed.path_hash_bytes} bytes`],
  ['Default region',!policy.scope_configured?'Not Station-managed':(policy.default_scope||'Unscoped')],
  ['Last contact sync',d.contact_sync?.sync_at?dt(d.contact_sync.sync_at):'No recent sync']
 ].map(([a,b])=>diagDetail(a,b)).join('');
 $('diag-transmissions').innerHTML=(d.transmissions||[]).length?d.transmissions.map(m=>{
  const proof=(m.evidence||[]).map(p=>`<li><time>${H(dt(p.ts))}</time><span>${H(p.label)}</span></li>`).join('');
  return `<details class="diag-message"><summary><span><b>${H(m.sender||'Local node')}</b> · ${H(m.kind==='channel'?'Channel '+m.destination:'Direct message')}<small>${H(m.text_preview)}</small></span><time>${H(dt(m.ts))}</time></summary><ol>${proof||'<li>No matching radio evidence recorded</li>'}</ol></details>`;
 }).join(''):empty('No outbound messages logged');
}
async function refreshDiagnostics(hours){
 if(!S.csrf)return;
 D08.data=await request(`/api/radio/diagnostics?hours=${Number(hours)||24}`);
 renderRadioDiagnostics();
}

// 0.8.1 — Message archive: server-side filters and timestamp/id cursor pagination.
// This is separate from the short recent-message list on Overview.
const HISTORY_SORT_LABELS088={newest:'newest first',oldest:'oldest first',channel_asc:'channel 0 → 7',channel_desc:'channel 7 → 0'};
const M081={items:[],total:0,cursor:null,loading:false,seq:0,signature:'',started:false,loadedMore:false};
function archiveChannelBucket088(m,descending=false){
 if(m.kind==='channel'&&/^[0-7]$/.test(String(m.target)))return Number(m.target);
 return descending?-1:8; // Direct/unknown items after all numbered channels.
}
function archiveCompare088(a,b,sort){
 if(sort.startsWith('channel_')){
  const descending=sort==='channel_desc';
  const channelDiff=archiveChannelBucket088(a,descending)-archiveChannelBucket088(b,descending);
  if(channelDiff)return descending?-channelDiff:channelDiff;
 }
 const timeDiff=new Date(a.ts).getTime()-new Date(b.ts).getTime();
 const diff=timeDiff||Number(a.id)-Number(b.id);
 return sort==='oldest'?diff:-diff;
}

function messageFilters081(){return {
 q:$('history-search').value.trim(), direction:$('history-direction').value,
 destination:$('history-destination').value, sort:$('history-sort').value
};}
function messageQuery081(filters,cursor){
 const qs=new URLSearchParams({limit:'50',...filters});
 if(cursor){qs.set('before_ts',cursor.before_ts);qs.set('before_id',String(cursor.before_id));if(cursor.before_channel!==undefined)qs.set('before_channel',String(cursor.before_channel));}
 return '/api/messages/history?'+qs.toString();
}
function compactTimestamp082(value){
 if(!value)return '—';
 const d=new Date(value);if(Number.isNaN(d.getTime()))return '—';
 const today=new Date();
 const opts=(today.toDateString()===d.toDateString())?{hour:'numeric',minute:'2-digit'}:{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'};
 return d.toLocaleString(undefined,opts);
}
// 0.8.6 — Use the radio's cached channel names in archived messages.
// The message records store a stable slot number, not a historical channel title.
// If an operator renames a slot, existing history intentionally shows its current name.
function channelName086(target){
 const index=Number(target);
 if(!Number.isInteger(index)||index<0||index>7)return 'Channel '+String(target??'?');
 const sources=[...(S.status?.channels||[]),...(S.channels?.slots||[])];
 const found=sources.find(c=>Number(c.index)===index&&String(c.name||'').trim());
 return found?String(found.name).trim():`Channel ${index}`;
}
// Reused by the Overview recent-message list and the Messages archive.
// A generic radio sender label is not a person: display the configured channel.
function messageDisplaySender086(m){
 const outgoing=m.direction==='out';
 const sender=outgoing?(m.sender&&m.sender!=='local'?m.sender:S.status?.radio_config?.name||'My station'):(m.sender||'Unknown sender');
 const generic=!outgoing&&m.kind==='channel'&&/^(channel|unknown(?: sender)?)$/i.test(String(m.sender||'').trim());
 return generic?channelName086(m.target):sender;
}
function channelNameSignature086(){
 return JSON.stringify(Array.from({length:8},(_,i)=>channelName086(i)));
}
function messageArchiveEntry081(m){
 const outgoing=m.direction==='out';
 const isChannel=m.kind==='channel';
 const originalSender=outgoing?(m.sender&&m.sender!=='local'?m.sender:S.status?.radio_config?.name||'My station'):(m.sender||'Unknown sender');
 const channelName=isChannel?channelName086(m.target):'';
 // Companion firmware may store the literal "channel" as the incoming sender.
 // Show the actual channel name in the row, without implying it is the sender's identity.
 const genericChannelSender=!outgoing&&isChannel&&/^(channel|unknown(?: sender)?)$/i.test(String(m.sender||'').trim());
 const author=messageDisplaySender086(m);
 const actualSender=genericChannelSender?(channelReplySender082(m)||'Not identified'):originalSender;
 const dest=isChannel?`${channelName} (#${m.target})`:'Direct';
 const status=outgoing?txLabel(m):'Received';
 const statusCss=!outgoing?'received':(/ack|repeat/i.test(status)?'verified':/fail/i.test(status)?'error':'unconfirmed');
 const evidence=(m.tx_evidence||[]).map(e=>{
  const label=({radio_accepted:'Radio accepted the send request',channel_echo:'Matching channel repeat heard · recipient unconfirmed',direct_ack:'Direct ACK received'})[e.kind]||e.kind;
  return `<li><time>${H(dt(e.ts))}</time><span>${H(label)}</span></li>`;
 }).join('');
 const replyLabel=m.kind==='channel'?'@ Reply':'Reply privately';
 return `<details class="message-row ${outgoing?'outbound':'inbound'}" data-message-id="${Number(m.id)}">
  <summary class="message-row-summary" title="Expand message details">
   <span class="message-row-direction" aria-label="${outgoing?'Sent':'Received'}" title="${outgoing?'Sent':'Received'}">${outgoing?'↗':'↙'}</span>
   <strong class="message-row-sender" title="${H(author)}">${H(author)}</strong>
   <span class="message-row-preview" title="${H(m.text)}">${H(m.text)}</span>
   <span class="message-row-target" title="${H(dest)}">${H(dest)}</span>
   <time class="message-row-time" datetime="${H(m.ts)}" title="${H(dt(m.ts))}">${H(compactTimestamp082(m.ts))}</time>
   <span class="message-row-caret" aria-hidden="true">⌄</span>
  </summary>
  <div class="message-row-expanded">
   <div class="message-row-top"><span class="message-state ${statusCss}">${H(status)}</span><span class="message-row-fulltime">${H(dt(m.ts))}</span></div>
   <p class="message-row-body">${H(m.text)}</p>
   <dl class="message-row-meta"><dt>From</dt><dd>${H(actualSender)}</dd><dt>Direction</dt><dd>${outgoing?'Outgoing':'Incoming'}</dd><dt>Conversation</dt><dd>${H(isChannel?dest:'Direct message')}</dd><dt>Status</dt><dd>${H(m.status)}</dd></dl>
   ${outgoing?`<div class="message-row-evidence"><strong>TX evidence</strong>${evidence?`<ul>${evidence}</ul>`:'<p>No matching radio evidence recorded. This does not mean the transmission failed.</p>'}</div>`:''}
   <div class="message-row-actions">
    ${!outgoing?`<button type="button" class="button primary message-reply" data-reply-message="${Number(m.id)}">↩ ${replyLabel}</button>`:''}
    <button type="button" class="button secondary" data-copy-message="${Number(m.id)}">Copy message</button>
   </div>
  </div>
 </details>`;
}
function renderMessageArchive081(){
 const open=new Set([...document.querySelectorAll('.message-row[open]')].map(n=>n.dataset.messageId));
 const el=$('all-messages');
 el.innerHTML=M081.items.length?M081.items.map(messageArchiveEntry081).join(''):empty('No messages match these filters.');
 el.querySelectorAll('[data-message-id]').forEach(n=>{if(open.has(n.dataset.messageId))n.open=true;});
 $('history-summary').textContent=`Showing ${M081.items.length.toLocaleString()} of ${M081.total.toLocaleString()} matching messages · ${HISTORY_SORT_LABELS088[$('history-sort').value]||'newest first'}`;
 $('history-more').hidden=!M081.cursor;
 $('history-more').disabled=M081.loading;
}
async function reloadMessageHistory(){
 if(!S.csrf)return;
 const seq=++M081.seq, filters=messageFilters081();
 M081.signature=JSON.stringify(filters);M081.loading=true;
 $('history-summary').textContent='Loading message history…';$('history-more').disabled=true;
 try{
  const data=await request(messageQuery081(filters));if(seq!==M081.seq)return;
  M081.items=data.items;M081.total=data.total;M081.cursor=data.next_cursor;M081.started=true;M081.loadedMore=false;
  renderMessageArchive081();
 }catch(e){if(seq===M081.seq){$('history-summary').textContent='History unavailable: '+e.message;toast(e.message,true);}}
 finally{if(seq===M081.seq){M081.loading=false;$('history-more').disabled=false;}}
}
async function loadOlderMessages081(){
 if(M081.loading||!M081.cursor)return;
 const seq=M081.seq, filters=messageFilters081();
 M081.loading=true;$('history-more').disabled=true;
 try{
  const page=await request(messageQuery081(filters,M081.cursor));if(seq!==M081.seq)return;
  const ids=new Set(M081.items.map(m=>m.id));for(const m of page.items)if(!ids.has(m.id)){M081.items.push(m);ids.add(m.id);}
  M081.total=page.total;M081.cursor=page.next_cursor;M081.loadedMore=true;renderMessageArchive081();
 }catch(e){if(seq===M081.seq)toast('Could not load older messages: '+e.message,true);}
 finally{if(seq===M081.seq){M081.loading=false;$('history-more').disabled=false;}}
}
async function refreshMessageHistoryTop081(){
 if(S.page!=='messages'||!M081.started||M081.loading)return;
 const filters=messageFilters081();if(JSON.stringify(filters)!==M081.signature)return;
 const seq=M081.seq;
 try{
  const data=await request(messageQuery081(filters));if(seq!==M081.seq)return;
  let rows;
  if(M081.loadedMore){
   const merged=new Map(M081.items.map(m=>[m.id,m]));
   for(const m of data.items)merged.set(m.id,m);
   rows=[...merged.values()].sort((a,b)=>archiveCompare088(a,b,filters.sort));
  }else rows=data.items;
  const changed=JSON.stringify(rows)!==JSON.stringify(M081.items)||M081.total!==data.total;
  M081.items=rows;M081.total=data.total;
  if(!M081.loadedMore)M081.cursor=data.next_cursor;
  if(changed)renderMessageArchive081();
 }catch(e){/* Keep history visible if the network briefly disconnects. */}
}
let historySearchTimer081=null;
$('history-search').addEventListener('input',()=>{clearTimeout(historySearchTimer081);historySearchTimer081=setTimeout(reloadMessageHistory,300)});
for(const field of ['history-direction','history-destination','history-sort'])$(field).addEventListener('change',reloadMessageHistory);
$('history-clear').addEventListener('click',()=>{$('history-search').value='';$('history-direction').value='all';$('history-destination').value='all';$('history-sort').value='newest';reloadMessageHistory();});
$('history-refresh').addEventListener('click',reloadMessageHistory);
$('history-more').addEventListener('click',loadOlderMessages081);
// Keep the archive fresh while the Messages page is open, without reloading older pages.
const refreshBefore081=refresh;
let lastChannelNames086='';
refresh=async function(){
 await refreshBefore081();
 if(S.page==='messages'){
  await refreshMessageHistoryTop081();
  const names=channelNameSignature086();
  if(names!==lastChannelNames086){lastChannelNames086=names;if(M081.started)renderMessageArchive081();}
 }
};


// 0.8.2 — Context-aware reply to an archived message. Plain @mentions on channels;
// direct replies must uniquely match a radio contact's public key or key prefix.
function resolveDirectSender082(sender){
 const value=String(sender||'').trim().toLowerCase();
 // Never resolve a direct-message identity by display name or a very short prefix.
 if(!/^[a-f0-9]{8,128}$/.test(value))return null;
 const matches=(S.contacts||[]).filter(c=>{
  const key=String(c.key||'').trim().toLowerCase();
  return key===value||(value.length>=8 && key.startsWith(value));
 });
 return matches.length===1?matches[0]:null;
}
// Channel message identities are carried in the firmware's text envelope:
// "Sender Name: message text". The sender field is often just "channel";
// it cannot be used as the @mention by itself.
function channelReplySender082(m){
 const envelope=/^([^:\r\n]{1,70}):\s*/.exec(String(m.text??''));
 const known=resolveDirectSender082(m.sender);
 const candidate=envelope?.[1] || known?.name || m.sender || '';
 const name=String(candidate).replace(/[\x00-\x1f\x7f]/g,'').trim().replace(/^@+/, '').slice(0,70);
 if(!name || /^(unknown(?: sender)?|channel|anonymous)$/i.test(name))return '';
 // Never turn an unresolved public-key prefix into a misleading username.
 if(!envelope && !known && /^[0-9a-f]{8,128}$/i.test(name))return '';
 return name;
}
function createReply082(id){
 const m=M081.items.find(x=>Number(x.id)===Number(id));
 if(!m || m.direction!=='in')return;
 let dest,body='',notice='';
 if(m.kind==='channel'){
  const channel=String(m.target??'');
  if(!/^[0-7]$/.test(channel)){toast('Original channel is unavailable for reply',true);return;}
  dest='channel:'+channel;
  const sender=channelReplySender082(m);
  if(sender)body='@'+sender+' ';
  notice=sender?`Reply to ${sender} on channel ${channel}`:`Reply on channel ${channel} (sender name unavailable)`;
 }else if(m.kind==='direct'){
  const match=resolveDirectSender082(m.sender);
  if(!match){toast('Direct sender is not uniquely identified in the T114 contacts. Sync contacts and choose the recipient manually.',true);return;}
  dest=match.key;
  notice=`Direct reply to ${match.name||short(match.key,14)}`;
 }else{toast('Cannot reply to this message type',true);return;}
 const select=$('destination');
 if(![...select.options].some(o=>o.value===dest)){
  toast(m.kind==='direct'?'Recipient is not available in the current radio contact list':'Channel is not available in the send composer',true);
  return;
 }
 const input=$('message-text'),old=input.value;
 if(old.trim() && select.value!==dest && !confirm('You have an unsent draft for another destination. Change destination and keep the draft?'))return;
 const composed=body && !old.startsWith(body)?body+old:old;
 if(composed.length>input.maxLength){toast('Reply mention plus existing draft exceeds the 180-character limit',true);return;}
 select.value=dest;input.value=composed;input.dispatchEvent(new Event('input',{bubbles:true}));
 $('reply-context-label').textContent=notice;
 $('reply-context').hidden=false;
 input.scrollIntoView({behavior:'smooth',block:'center'});
 input.focus({preventScroll:true});input.setSelectionRange(input.value.length,input.value.length);
}
$('all-messages').addEventListener('click',async event=>{
 const reply=event.target.closest('[data-reply-message]');
 if(reply){createReply082(reply.dataset.replyMessage);return;}
 const copy=event.target.closest('[data-copy-message]');
 if(copy){
  const m=M081.items.find(x=>Number(x.id)===Number(copy.dataset.copyMessage));
  if(!m)return;
  try{await navigator.clipboard.writeText(m.text);toast('Message copied');}
  catch{toast('Browser blocked copying. Select and copy the expanded message text.',true);}
 }
});
$('reply-cancel').addEventListener('click',()=>{$('reply-context').hidden=true;});


// 0.8.4 — telemetry trends. Everything comes from PostgreSQL, not a second serial connection.
const TR084={data:null,location:null,adverts:null};
function trendFmt084(v,digits=1){return typeof v==='number'&&Number.isFinite(v)?v.toFixed(digits):'—'}
function durationFmt089(seconds){
 if(typeof seconds!=='number'||!Number.isFinite(seconds)||seconds<0)return '—';
 const total=Math.floor(seconds/60);
 const days=Math.floor(total/1440),hours=Math.floor((total%1440)/60),minutes=total%60;
 return [days?days+'d':'',hours?hours+'h':'',(!days&&!hours||minutes)?minutes+'m':''].filter(Boolean).join(' ');
}
function trendSvg084(id,points,keys,colors,unit){
 const parent=$(id);if(!parent)return;
 if(!points.length || !keys.some(k=>points.some(p=>typeof p[k]==='number'))){parent.innerHTML=empty('No measurement available for this interval');return}
 const w=760,h=212,pad=42,low=14,wide=w-2*pad,tall=h-2*pad;
 const all=points.flatMap(p=>keys.map(k=>p[k]).filter(v=>typeof v==='number'&&Number.isFinite(v)));
 let min=Math.min(...all),max=Math.max(...all);if(min===max){min-=1;max+=1}
 const margin=(max-min)*.10;min-=margin;max+=margin;
 const px=i=>pad+(points.length<=1?wide/2:wide*i/(points.length-1));
 const py=v=>h-pad-(v-min)/(max-min)*tall;
 let grid='';for(let i=0;i<4;i++){const y=low+15+i*49;grid+=`<line x1="${pad}" x2="${w-pad}" y1="${y}" y2="${y}" stroke="#34505b" stroke-dasharray="4 5"/><text x="3" y="${y+4}" fill="#99b4c2" font-size="12">${keys.length===1&&keys[0]==='uptime_secs'?durationFmt089(Math.max(0,max-(y-(h-pad-tall))/tall*(max-min))):(max-(y-(h-pad-tall))/tall*(max-min)).toFixed(1)}</text>`;}
 const lines=keys.map((key,j)=>{let segments=[],run=[];const add=()=>{if(run.length>0){segments.push(run.join(' '));run=[]}};
  points.forEach((p,i)=>{const v=p[key];if(typeof v!=='number'||p.reset&&key.includes('per_min'))add();else run.push(px(i).toFixed(1)+','+py(v).toFixed(1))});add();
  return segments.map(segment=>`<polyline points="${segment}" fill="none" stroke="${colors[j]}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>`).join('');}).join('');
 const marks=points.map((p,i)=>p.reset?`<line x1="${px(i)}" x2="${px(i)}" y1="${low}" y2="${h-pad}" stroke="#f59d6e" stroke-dasharray="4 3"/>`:'').join('');
 const legend=keys.map((k,i)=>`<span><i style="background:${colors[i]}"></i>${H(k.replaceAll('_',' '))}</span>`).join('');
 parent.innerHTML=`<div class="trend-legend">${legend}<small>${H(unit)}</small></div><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${H(keys.join(' and '))} history">${grid}${lines}${marks}</svg><div class="trend-axis"><span>${H(new Date(points[0].ts).toLocaleString())}</span><span>${H(new Date(points[points.length-1].ts).toLocaleString())}</span></div>`;
}
function renderTrends084(){const d=TR084.data;if(!d)return;const p=d.points||[],last=[...p].reverse().find(x=>x.rx_per_min!==null||x.tx_per_min!==null)||{};
 $('trend-rx').textContent=trendFmt084(last.rx_per_min);$('trend-tx').textContent=trendFmt084(last.tx_per_min);
 $('monitor-error-rate').textContent=trendFmt084([...p].reverse().find(x=>x.errors_per_min!==null&&x.errors_per_min!==undefined)?.errors_per_min);
 $('trend-resets').textContent=String(d.reset_count??0);$('trend-uptime').textContent=durationFmt089(d.latest?.uptime_secs);
 trendSvg084('trend-traffic',p,['rx_per_min','tx_per_min'],['#42d7bf','#f0ac52'],'packets/min');
 trendSvg084('trend-paths',p,['flood_rx_per_min','direct_rx_per_min','flood_tx_per_min','direct_tx_per_min'],['#42d7bf','#75b9e8','#ffb356','#b7a1fc'],'packets/min');
 trendSvg084('trend-errors',p,['errors_per_min'],['#eb857c'],'errors/min');
 trendSvg084('trend-rf',p,['rssi_dbm','noise_floor_dbm'],['#75b9e8','#42d7bf'],'dBm');
 trendSvg084('trend-snr',p,['snr_db'],['#b7a1fc'],'dB');
 trendSvg084('trend-uptime-chart',p,['uptime_secs'],['#f0ac52'],'uptime');
 $('trend-reset-list').innerHTML=d.resets?.length?d.resets.slice(-8).reverse().map(x=>`<div class="radio-reset">↻ ${H(dt(x.ts))} · ${H(x.reason)}</div>`).join(''):'No uptime or counter reset detected in this time window.';
}
async function refreshTrends084(hours){if(!S.csrf)return;TR084.data=await request('/api/radio/trends?hours='+Number(hours||24));renderTrends084()}
function renderOwn084(){const own=TR084.location,ad=TR084.adverts;if(own){$('own-radio-name').textContent=own.node_name||'My node';
 const saved=own.private||{},observed=own.radio||{},fields=observed.readback||{};
 $('own-location-status').innerHTML=[['Private map location',saved.latitude!=null?`${Number(saved.latitude).toFixed(5)}, ${Number(saved.longitude).toFixed(5)}`:'Not saved'],['T114 policy readback',observed.policy_verified?(String(fields.adv_loc_policy??fields.advert_loc_policy)==='1'?'Location included':'Location hidden'):'Unavailable / unknown'],['Last radio action',observed.last_write_mode||'None from this interface']].map(([k,v])=>`<div class="health-detail"><span>${H(k)}</span><b>${H(v)}</b></div>`).join('');
 }
 if(ad){$('advert-local-cooldown').textContent=ad.cooldown_local_secs?`Cooldown: ${Math.ceil(ad.cooldown_local_secs/60)} min`:'Ready to request';$('advert-flood-cooldown').textContent=ad.cooldown_flood_secs?`Cooldown: ${Math.ceil(ad.cooldown_flood_secs/60)} min`:'Ready to request';
 $('advert-local').disabled=!!(ad.cooldown_local_secs||ad.pending?.length);$('advert-flood').disabled=!!(ad.cooldown_flood_secs||ad.pending?.length);
 const entries=[...(ad.pending||[]).map(x=>({ts:null,mode:x.mode,kind:'pending'})),...(ad.events||[])];
 $('advert-history').innerHTML=entries.length?entries.slice(0,16).map(x=>`<div class="rx-line"><time>${H(dt(x.ts))}</time><b>${H(x.mode||'local')}</b><span>${H(x.kind)}</span></div>`).join(''):empty('No advertisement requests recorded.');}}
async function refreshOwn084(prefill=false){if(!S.csrf)return;const [loc,ad]=await Promise.all([request('/api/node/location'),request('/api/node/adverts')]);TR084.location=loc;TR084.adverts=ad;
 if(prefill&&loc.private){$('own-lat').value=loc.private.latitude??'';$('own-lon').value=loc.private.longitude??'';$('own-elevation').value=loc.private.elevation_m??'';$('own-description').value=loc.private.description||'';}renderOwn084();}
$('own-location-form').addEventListener('submit',async e=>{e.preventDefault();try{await request('/api/node/location',{method:'PUT',body:JSON.stringify({latitude:Number($('own-lat').value),longitude:Number($('own-lon').value),description:$('own-description').value,elevation_m:$('own-elevation').value===''?null:Number($('own-elevation').value)})});toast('Saved privately. Radio was not changed.');await refreshOwn084();await refresh()}catch(err){toast(err.message,true)}});
async function applyOwn084(mode){const confirmText={share:'SHARE LOCATION',private:'APPLY PRIVATE',hide:'HIDE LOCATION'}[mode];
 const typed=prompt(`Confirm ${mode} radio action. Type ${confirmText}:`);if(typed!==confirmText)return;
 try{const x=await request('/api/node/location/apply',{method:'POST',body:JSON.stringify({mode,confirm:typed})});await pollCommand(x.id);toast('T114 accepted location command');await refreshOwn084();await refresh()}catch(e){toast(e.message,true)}}
$('own-apply-private').addEventListener('click',()=>applyOwn084('private'));
$('own-share').addEventListener('click',()=>applyOwn084('share'));
$('own-hide').addEventListener('click',()=>applyOwn084('hide'));
async function sendAdvert084(flood){const confirmText=flood?'FLOOD ADVERT':'LOCAL ADVERT';const typed=prompt(`Send ${flood?'network-wide flood':'zero-hop local'} advertisement? Type ${confirmText}:`);if(typed!==confirmText)return;
 try{const x=await request('/api/node/adverts',{method:'POST',body:JSON.stringify({flood,confirm:typed})});toast('Advertisement queued #'+x.id);await pollCommand(x.id);toast('Radio accepted advertisement; delivery unconfirmed');await refreshOwn084()}catch(err){toast(err.message,true)}}
$('advert-local').addEventListener('click',()=>sendAdvert084(false));$('advert-flood').addEventListener('click',()=>sendAdvert084(true));
$('advert-refresh').addEventListener('click',()=>refreshOwn084().catch(e=>toast(e.message,true)));
// 0.8.5: one monitoring page and one history selector; all reads use existing API endpoints.
const MON085={generation:0};
async function refreshMonitor085(){
 if(!S.csrf || S.page!=='monitor')return;
 const generation=++MON085.generation, hours=Number($('monitor-window').value)||24;
 const [trends,diagnostics]=await Promise.all([
  request('/api/radio/trends?hours='+hours),
  request('/api/radio/diagnostics?hours='+hours)
 ]);
 if(generation!==MON085.generation || S.page!=='monitor' || hours!==Number($('monitor-window').value))return;
 TR084.data=trends;D08.data=diagnostics;renderTrends084();renderRadioDiagnostics();
}
$('monitor-window').addEventListener('change',()=>refreshMonitor085().catch(e=>toast(e.message,true)));
$('monitor-refresh').addEventListener('click',()=>refreshMonitor085().catch(e=>toast(e.message,true)));
// Only fetch additional diagnostics while their combined page is visible.
const navigateBefore085=navigate;
navigate=function(view){
 if(['health','diagnostics','telemetry'].includes(view))view='monitor';
 navigateBefore085(view);
 if(view==='monitor')refreshMonitor085().catch(e=>toast(e.message,true));
 if(view==='my-node')refreshOwn084(true).catch(e=>toast(e.message,true));
};
const refreshBefore085=refresh;
refresh=async function(){
 await refreshBefore085();
 if(S.page==='monitor')await refreshMonitor085().catch(e=>toast(e.message,true));
 if(S.page==='my-node')await refreshOwn084(false).catch(e=>toast(e.message,true));
};

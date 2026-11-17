'use strict';
const $ = (id) => document.getElementById(id);
const S = {csrf:null, page:'overview', contacts:[], messages:[], events:[], alerts:[], history:[], jobs:[], mapNodes:[], health:null, channels:{slots:[]}, addressBook:[], rxLog:[], routing:null, routingCatalog:null, status:null};
const H = (v) => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt = (v) => v ? new Date(v).toLocaleString() : '—';
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
function showLogin(){S.csrf=null;$('shell').hidden=true;$('login-screen').hidden=false}
function showApp(){ $('login-screen').hidden=true;$('shell').hidden=false }
function navigate(view){S.page=view;document.querySelectorAll('.view').forEach(e=>e.hidden=e.id!=='view-'+view);document.querySelectorAll('[data-view]').forEach(e=>e.classList.toggle('active',e.dataset.view===view));$('page-title').textContent=({overview:'Overview',messages:'Messages',nodes:'Nodes & Contacts',telemetry:'Telemetry',alerts:'Alerts',events:'Event Log',firmware:'Firmware Manager',map:'Node Map',radio:'Radio Settings',health:'Radio Health',channels:'Channel Management',address:'Address Book',digest:'Email Digests',routing:'Routing & Regions'})[view];render();if(view==='map')requestAnimationFrame(()=>requestAnimationFrame(updateMap));if(view==='digest')loadDigest();}
function empty(text){return `<div class="empty">${H(text)}</div>`}
function nodeStyle(role){
  const roleKey=String(role||'unknown').toLowerCase().replaceAll(' ','_');
  return ({repeater:['repeater','↗','Repeater'],client:['client','●','Companion'],room_server:['room_server','▣','Room server'],sensor:['sensor','◆','Sensor']})[roleKey]||['unknown','?','Unknown'];
}
function nodeTag(role){const [css,icon,label]=nodeStyle(role);return `<span class="node-tag ${css}"><span aria-hidden="true">${icon}</span> ${H(label)}</span>`}
function messageStatus(v){return ({sent:'Radio accepted · delivery unconfirmed',sent_unconfirmed:'Radio accepted · delivery unconfirmed',acknowledged:'Acknowledged',simulated:'Simulated'})[v]||String(v||'')}
function messageHeading(m){const node=(m.direction==='out')?(m.sender&&m.sender!=='local'?m.sender:S.status?.radio_config?.name||'Local node'):(m.sender||'Unknown');return `${m.kind==='channel'?'#'+m.target:'Direct'} · ${m.direction==='in'?'Received':'Sent'} · ${node}`}
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
function render(){if(!$('shell') || $('shell').hidden || !S.status)return;
 const st=S.status, radio=st.radio||{};$('mode-badge').textContent='USB SERIAL';$('mode-badge').className='pill';$('connection-badge').textContent=radio.connected?'● Connected':'● Offline';$('connection-badge').className='pill '+(radio.connected?'':'red');$('kpi-radio').textContent=radio.connected?'Online':'Offline';$('kpi-device').textContent=radio.error||radio.device||'Awaiting device';$('kpi-nodes').textContent=st.counts.contacts;const sync=st.contact_sync||{};const syncText=typeof sync.radio_contacts==='number'?`${sync.radio_contacts} on radio · +${sync.new_in_sync||0} new at last sync`:'Awaiting radio contact sync';$('nodes-kpi-detail').textContent=syncText;$('contact-sync-summary').textContent=`${syncText}${sync.sync_at?' · '+dt(sync.sync_at):''}. RX packets do not increase this count automatically.`;$('kpi-messages').textContent=st.counts.messages;$('power-title').textContent=st.power_source==='usb'?'POWER SOURCE':'BATTERY';$('kpi-battery').textContent=st.power_source==='usb'?'USB Powered':(st.sample?.battery_pct!=null ? st.sample.battery_pct.toFixed(0)+'%' : '—');$('kpi-battery').style.fontSize=st.power_source==='usb'?'1.35rem':'';$('power-caption').textContent=st.power_source==='usb'?'No battery installed':'Most recent telemetry';$('battery-panel').hidden=st.power_source==='usb';
 const rec=S.messages.slice(0,7);$('recent-messages').innerHTML=rec.length?rec.map(m=>item(messageHeading(m),m.text,m.ts,m.direction)).join(''):empty('No messages yet');
 $('all-messages').innerHTML=S.messages.length?S.messages.map(m=>item(messageHeading(m),`${m.text} · ${messageStatus(m.status)}`,m.ts,m.direction)).join(''):empty('No messages yet');
 $('recent-nodes').innerHTML=S.contacts.length?S.contacts.slice(0,6).map(n=>`<div class="node-row">${nodeTag(n.role)}${item(n.name,short(n.key,36),n.last_seen)}</div>`).join(''):empty('No contacts discovered');
 $('contacts-table').innerHTML=S.contacts.length?S.contacts.map(n=>`<tr><td>${H(n.name)}</td><td>${nodeTag(n.role)}</td><td><code title="${H(n.key)}">${H(short(n.key,40))}</code></td><td>${H(dt(n.last_seen))}</td><td><button class="subtle" type="button" data-save-contact="${H(n.key)}">Save ↗</button></td></tr>`).join(''):`<tr><td colspan="5">No contacts discovered yet</td></tr>`;
 $('recent-alerts').innerHTML=S.alerts.filter(a=>!a.resolved).length?S.alerts.filter(a=>!a.resolved).slice(0,5).map(a=>item(a.severity.toUpperCase(),a.message,a.ts,'danger')).join(''):empty('No active alerts');
 $('all-alerts').innerHTML=S.alerts.length?S.alerts.map(a=>`<div class="stream-item"><span class="dot ${a.resolved?'':'danger'}"></span><div class="stream-main"><div class="stream-head"><b>${H(a.severity.toUpperCase())}</b><span class="stream-time">${H(dt(a.ts))}</span></div><p class="stream-body">${H(a.message)}</p></div>${a.resolved?'<span class="pill">Resolved</span>':`<button class="button secondary" data-resolve="${a.id}">Resolve</button>`}</div>`).join(''):empty('No alerts');
 $('event-list').innerHTML=S.events.length?S.events.map(e=>item(e.kind,JSON.stringify(e.detail),e.ts)).join(''):empty('No radio events');
 $('telemetry-info').textContent=JSON.stringify({radio,latest:st.sample,known_contacts:st.counts.contacts,logged_messages:st.counts.messages,raw_radio_stats:st.last_stats},null,2);
 plot('overview-chart',S.history,'noise','dBm');plot('noise-chart',S.history,'noise','dBm');if(st.power_source!=='usb')plot('battery-chart',S.history,'battery','%');plot('rx-chart',S.history,'packets_rx','packets');plot('rssi-chart',S.history,'rssi','dBm');
 $('firmware-jobs').innerHTML=S.jobs.length?S.jobs.map(j=>`<div class="stream-item"><span class="dot ${['failed','error'].includes(j.status)?'danger':j.status==='complete'?'':'warn'}"></span><div class="stream-main"><div class="stream-title">${H(j.filename||j.id)}</div><div class="stream-body">${H(j.status)} · ${H(j.message||'')}</div></div><button class="subtle" data-job="${H(j.id)}">Logs</button></div>`).join(''):empty('No firmware updates yet');
 $('radio-channel-list').textContent=(st.channels||[]).map(c=>`${c.index}: ${c.name||'(empty)'}`).join(' · ')||'No channel information';$('last-refresh').textContent='Refreshed '+new Date().toLocaleTimeString();fillDestinations();
}
let loading=false;
async function refresh(){if(!S.csrf || loading)return;loading=true;try{
  const [st,contacts,msg,events,alerts,hist,jobs,mapNodes,health,channels,addressBook,rxLog]=await Promise.all([request('/api/status'),request('/api/contacts'),request('/api/messages?limit=300'),request('/api/events?limit=100'),request('/api/alerts'),request('/api/history?hours=24'),request('/api/firmware/jobs'),request('/api/map/nodes'),request('/api/radio/health'),request('/api/channels'),request('/api/address-book'),request('/api/radio/rx-log?limit=150')]);
  Object.assign(S,{status:st,contacts,messages:msg,events,alerts,history:hist,jobs,mapNodes,health,channels,addressBook,rxLog});render();renderHealth();renderChannels();renderAddressBook();renderRxLog();if(S.page==='map')updateMap();
}catch(e){toast(e.message,true)}finally{loading=false}}
async function enqueue(payload){const x=await request('/api/commands',{method:'POST',body:JSON.stringify(payload)});toast('Command queued #'+x.id);const deadline=Date.now()+20000;while(Date.now()<deadline){await new Promise(r=>setTimeout(r,1200));let y=await request('/api/commands/'+x.id);if(y.state==='failed')throw Error(y.error);if(y.state==='complete'){toast('Radio command accepted');await refresh();return y}}
 toast('Command queued. Check activity for results.')}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';const form=new FormData(e.target);try{const res=await request('/api/login',{method:'POST',body:JSON.stringify({username:form.get('username'),password:form.get('password')})});S.csrf=res.csrf;showApp();$('grafana-link').href=`${location.protocol}//${location.hostname}:3300`;await refresh()}catch(err){$('login-error').textContent=err.message}});
document.querySelectorAll('[data-view]').forEach(e=>e.addEventListener('click',()=>navigate(e.dataset.view)));
document.querySelectorAll('.go-messages').forEach(e=>e.addEventListener('click',()=>navigate('messages')));
$('logout').addEventListener('click',async()=>{try{await request('/api/logout',{method:'POST'})}finally{showLogin()}});
$('logout-mobile').addEventListener('click',()=>{$('logout').click()});
$('refresh').addEventListener('click',refresh);
$('message-text').addEventListener('input',()=>{$('char-count').textContent=$('message-text').value.length+' / 180'});
$('send-form').addEventListener('submit',async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await enqueue({kind:'send',destination:$('destination').value,text:$('message-text').value});$('message-text').value='';$('char-count').textContent='0 / 180'}catch(err){toast(err.message,true)}finally{b.disabled=false}});
for(const id of ['sync-contacts','overview-discover'])$(id).addEventListener('click',async()=>{try{await enqueue({kind:'contacts'})}catch(e){toast(e.message,true)}});
$('advertise').addEventListener('click',async()=>{try{await enqueue({kind:'advert',flood:false})}catch(e){toast(e.message,true)}});
$('all-alerts').addEventListener('click',async e=>{let id=e.target.dataset.resolve;if(!id)return;try{await request('/api/alerts/'+id+'/resolve',{method:'POST'});await refresh()}catch(err){toast(err.message,true)}});
$('firmware-form').addEventListener('submit',async e=>{e.preventDefault();if(!confirm('This will stop the collector and flash the T114. Continue?'))return;let btn=e.submitter;btn.disabled=true;try{const f=new FormData();f.append('file',$('firmware-file').files[0]);f.append('confirmation',$('flash-confirm').value);let job=await request('/api/firmware/upload',{method:'POST',body:f});toast('Firmware job queued: '+job.id);$('firmware-form').reset();await refresh();await showJob(job.id)}catch(err){toast(err.message,true)}finally{btn.disabled=false}});
async function showJob(id){try{let j=await request('/api/firmware/jobs/'+id);$('firmware-log').textContent=`${j.status}: ${j.message||''}\nSHA256: ${j.sha256||''}\n\n${j.log||'No flashing output yet.'}`}catch(e){toast(e.message,true)}}
$('firmware-jobs').addEventListener('click',e=>{const id=e.target.dataset.job;if(id)showJob(id)});
$('export-messages').addEventListener('click',async e=>{e.preventDefault();try{const res=await fetch('/api/export/messages.csv',{credentials:'same-origin'});if(!res.ok)throw Error('Export failed');const blob=await res.blob();let u=URL.createObjectURL(blob);let a=document.createElement('a');a.href=u;a.download='meshcore-messages.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),3000)}catch(err){toast(err.message,true)}});
(async()=>{try{let me=await request('/api/me');S.csrf=me.csrf;showApp();$('grafana-link').href=`${location.protocol}//${location.hostname}:${me.grafana_port}`;await refresh()}catch{showLogin()}})();
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
 $('health-rx').textContent=show(d.rx);$('health-tx').textContent=show(d.tx);$('health-errors').textContent=show(d.rx_errors);
 $('health-age').textContent=typeof h.sample_age_secs==='number'?`${h.sample_age_secs}s`:'—';
 $('health-freshness').textContent=h.sample_fresh?'Recent telemetry':'Telemetry delayed/stale';
 $('health-details').innerHTML=[['Collector',h.connected?'Connected':'Disconnected'],['Power','USB (no battery)'],['Radio uptime',show(d.uptime_secs)+' s'],['Flood RX',show(d.flood_rx)],['Direct RX',show(d.direct_rx)],['Flood TX',show(d.flood_tx)],['Direct TX',show(d.direct_tx)],['RX airtime',show(d.rx_air_secs)+' s'],['TX airtime',show(d.tx_air_secs)+' s'],['Noise floor',show(d.noise_floor)+' dBm'],['Last RSSI',show(d.rssi)+' dBm'],['Receive errors',show(d.rx_errors)],['New RX since last sample',show(h.deltas?.rx)],['New RX errors since last sample',show(h.deltas?.rx_errors)]].map(([k,v])=>`<div class="health-detail"><span>${H(k)}</span><b>${H(v)}</b></div>`).join('');
 $('health-tx-note').textContent='Flood TX: '+show(d.flood_tx)+' · Direct TX: '+show(d.direct_tx)+' · Counts only; other stations have not been confirmed to hear these transmissions.';
  plot('health-rx-chart',S.history,'packets_rx','packets');plot('health-tx-chart',S.history,'packets_tx','packets');plot('health-error-chart',S.history,'rx_errors','errors');
}
function renderChannels(){const slots=S.channels?.slots||[];
 $('channels-table').innerHTML=slots.map(c=>`<tr><td>#${c.index}</td><td>${H(c.name||'—')}</td><td>${c.configured?'Configured':'Empty'}</td><td><button class="subtle" type="button" data-edit-channel="${c.index}">Edit</button></td></tr>`).join('');
 const opts=slots.map(c=>`<option value="${c.index}">#${c.index} · ${H(c.name||'(empty)')}</option>`).join('');
 for(const id of ['channel-slot','channel-delete-slot']){const e=$(id),old=e.value;if(e.innerHTML!==opts){e.innerHTML=opts;if(slots.some(c=>String(c.index)===old))e.value=old}}
}
$('channels-table').addEventListener('click',e=>{const idx=e.target.dataset.editChannel;if(idx===undefined)return;
 $('channel-slot').value=idx;$('channel-name').value=S.channels.slots.find(c=>String(c.index)===idx)?.name||'';$('channel-key').value='';$('channel-name').focus()});
$('channel-delete-slot').addEventListener('change',e=>{$('channel-delete-confirm').placeholder='DELETE CHANNEL '+e.target.value});
$('channel-form').addEventListener('submit',async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;
 try{const idx=Number($('channel-slot').value),name=$('channel-name').value.trim(),secret=$('channel-key').value.trim();
 if(secret && !/^[0-9a-fA-F]{32}$/.test(secret))throw Error('Secret must be 32 hex characters');
 if(!confirm(`Save channel ${idx} (${name}) to the physical T114?${secret?' This will replace the existing key.':''}`))return;
 const x=await request('/api/channels/'+idx,{method:'PUT',body:JSON.stringify({name,secret_hex:secret||null,confirm:$('channel-confirm').value})});
 await pollCommand(x.id);$('channel-key').value='';$('channel-confirm').value='';toast('Channel saved to radio');await refresh();
 }catch(err){toast(err.message,true)}finally{btn.disabled=false}});
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
    $('digest-worker-status').textContent=x.worker_online?'● Scheduler online':'● Scheduler offline';
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

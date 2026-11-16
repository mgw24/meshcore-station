'use strict';
const $ = (id) => document.getElementById(id);
const S = {csrf:null, page:'overview', contacts:[], messages:[], events:[], alerts:[], history:[], jobs:[], status:null};
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
function navigate(view){S.page=view;document.querySelectorAll('.view').forEach(e=>e.hidden=e.id!=='view-'+view);document.querySelectorAll('[data-view]').forEach(e=>e.classList.toggle('active',e.dataset.view===view));$('page-title').textContent=({overview:'Overview',messages:'Messages',nodes:'Nodes & Contacts',telemetry:'Telemetry',alerts:'Alerts',events:'Event Log',firmware:'Firmware Manager'})[view];render();}
function empty(text){return `<div class="empty">${H(text)}</div>`}
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
 const st=S.status, radio=st.radio||{};$('mode-badge').textContent=st.simulation?'SIMULATION':'USB SERIAL';$('mode-badge').className='pill '+(st.simulation?'amber':'');$('connection-badge').textContent=radio.connected?'● Connected':'● Offline';$('connection-badge').className='pill '+(radio.connected?'':'red');$('kpi-radio').textContent=radio.connected?'Online':'Offline';$('kpi-device').textContent=radio.error||radio.device||'Awaiting device';$('kpi-nodes').textContent=st.counts.contacts;$('kpi-messages').textContent=st.counts.messages;$('kpi-battery').textContent=st.sample?.battery_pct!=null ? st.sample.battery_pct.toFixed(0)+'%' : '—';
 const rec=S.messages.slice(0,7);$('recent-messages').innerHTML=rec.length?rec.map(m=>item(m.kind==='channel'?`#${m.target} · ${m.direction==='in'?'Received':'Sent'}`:`${m.direction==='in'?'From':'To'} ${short(m.direction==='in'?m.sender:m.target)}`,m.text,m.ts,m.direction)).join(''):empty('No messages yet');
 $('all-messages').innerHTML=S.messages.length?S.messages.map(m=>item(`${m.kind==='channel'?'#'+m.target:short(m.direction==='in'?m.sender:m.target,35)} · ${m.direction==='in'?'Incoming':'Outgoing'}`,`${m.text} · ${m.status}`,m.ts,m.direction)).join(''):empty('No messages yet');
 $('recent-nodes').innerHTML=S.contacts.length?S.contacts.slice(0,6).map(n=>item(n.name,`${n.role} · ${short(n.key,36)}`,n.last_seen)).join(''):empty('No contacts discovered');
 $('contacts-table').innerHTML=S.contacts.length?S.contacts.map(n=>`<tr><td>${H(n.name)}</td><td>${H(n.role)}</td><td><code title="${H(n.key)}">${H(short(n.key,40))}</code></td><td>${H(dt(n.last_seen))}</td></tr>`).join(''):`<tr><td colspan="4">No contacts discovered yet</td></tr>`;
 $('recent-alerts').innerHTML=S.alerts.filter(a=>!a.resolved).length?S.alerts.filter(a=>!a.resolved).slice(0,5).map(a=>item(a.severity.toUpperCase(),a.message,a.ts,'danger')).join(''):empty('No active alerts');
 $('all-alerts').innerHTML=S.alerts.length?S.alerts.map(a=>`<div class="stream-item"><span class="dot ${a.resolved?'':'danger'}"></span><div class="stream-main"><div class="stream-head"><b>${H(a.severity.toUpperCase())}</b><span class="stream-time">${H(dt(a.ts))}</span></div><p class="stream-body">${H(a.message)}</p></div>${a.resolved?'<span class="pill">Resolved</span>':`<button class="button secondary" data-resolve="${a.id}">Resolve</button>`}</div>`).join(''):empty('No alerts');
 $('event-list').innerHTML=S.events.length?S.events.map(e=>item(e.kind,JSON.stringify(e.detail),e.ts)).join(''):empty('No radio events');
 $('telemetry-info').textContent=JSON.stringify({radio,latest:st.sample,known_contacts:st.counts.contacts,logged_messages:st.counts.messages,raw_radio_stats:st.last_stats},null,2);
 plot('overview-chart',S.history,'noise','dBm');plot('noise-chart',S.history,'noise','dBm');plot('battery-chart',S.history,'battery','%');plot('rx-chart',S.history,'packets_rx','packets');plot('rssi-chart',S.history,'rssi','dBm');
 $('firmware-jobs').innerHTML=S.jobs.length?S.jobs.map(j=>`<div class="stream-item"><span class="dot ${['failed','error'].includes(j.status)?'danger':j.status==='complete'?'':'warn'}"></span><div class="stream-main"><div class="stream-title">${H(j.filename||j.id)}</div><div class="stream-body">${H(j.status)} · ${H(j.message||'')}</div></div><button class="subtle" data-job="${H(j.id)}">Logs</button></div>`).join(''):empty('No firmware updates yet');
 $('last-refresh').textContent='Refreshed '+new Date().toLocaleTimeString();fillDestinations();
}
let loading=false;
async function refresh(){if(!S.csrf || loading)return;loading=true;try{
  const [st,contacts,msg,events,alerts,hist,jobs]=await Promise.all([request('/api/status'),request('/api/contacts'),request('/api/messages?limit=300'),request('/api/events?limit=100'),request('/api/alerts'),request('/api/history?hours=24'),request('/api/firmware/jobs')]);
  Object.assign(S,{status:st,contacts,messages:msg,events,alerts,history:hist,jobs});render();
}catch(e){toast(e.message,true)}finally{loading=false}}
async function enqueue(payload){const x=await request('/api/commands',{method:'POST',body:JSON.stringify(payload)});toast('Command queued #'+x.id);const deadline=Date.now()+20000;while(Date.now()<deadline){await new Promise(r=>setTimeout(r,1200));let y=await request('/api/commands/'+x.id);if(y.state==='failed')throw Error(y.error);if(y.state==='complete'){toast(y.result?.simulated?'Simulated command completed':'Radio command accepted');await refresh();return y}}
 toast('Command queued. Check activity for results.')}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();$('login-error').textContent='';const form=new FormData(e.target);try{const res=await request('/api/login',{method:'POST',body:JSON.stringify({username:form.get('username'),password:form.get('password')})});S.csrf=res.csrf;showApp();$('grafana-link').href=`${location.protocol}//${location.hostname}:3300`;await refresh()}catch(err){$('login-error').textContent=err.message}});
document.querySelectorAll('[data-view]').forEach(e=>e.addEventListener('click',()=>navigate(e.dataset.view)));
document.querySelectorAll('.go-messages').forEach(e=>e.addEventListener('click',()=>navigate('messages')));
$('logout').addEventListener('click',async()=>{try{await request('/api/logout',{method:'POST'})}finally{showLogin()}});
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

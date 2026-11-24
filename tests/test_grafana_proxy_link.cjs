'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const js=fs.readFileSync('static/app.js','utf8');
const backend=fs.readFileSync('station/web.py','utf8');
const compose=fs.readFileSync('compose.yaml','utf8');
const html=fs.readFileSync('static/index.html','utf8');

function section(start,end){
  const a=js.indexOf(start),b=js.indexOf(end,a);
  assert(a>=0&&b>a,`Missing Grafana helper section ${start}`);
  return js.slice(a,b);
}
const context={URL};
vm.createContext(context);
vm.runInContext(section('function grafanaLinkUrl(', 'function setGrafanaLink('),context);
const select=(data,location)=>context.grafanaLinkUrl(data,location);
const local={protocol:'http:',hostname:'station.local'};
const proxied={protocol:'https:',hostname:'station.example'};
assert.equal(select({grafana_url:'https://metrics.example/',grafana_port:3300},proxied),'https://metrics.example/');
assert.equal(select({grafana_url:'https://metrics.example/grafana/',grafana_port:3300},proxied),'https://metrics.example/grafana/');
assert.equal(select({grafana_url:'',grafana_port:3300},local),'http://station.local:3300/');
assert.equal(select({grafana_url:null,grafana_port:3301},local),'http://station.local:3301/');
assert.equal(select({grafana_url:'javascript:alert(1)',grafana_port:3300},local),'http://station.local:3300/');
assert.equal(select({grafana_url:'https://name:password@metrics.example/',grafana_port:3300},local),'http://station.local:3300/');
assert.match(js,/const me=await request\('\/api\/me'\);setGrafanaLink\(me\);await refresh\(\)/,'Fresh login must configure Grafana link');
assert.match(js,/S.csrf=me.csrf;showApp\(\);setGrafanaLink\(me\);await refresh\(\)/,'Session restore must configure Grafana link');
assert.match(backend,/['"]grafana_url['"]:\s*grafana_public_url\(\)/);
assert.match(compose,/GF_SERVER_ROOT_URL:.*GRAFANA_PUBLIC_URL/);
assert.match(html,/app\.js\?v=088-grafana-proxy-1/,'Updated script must bypass existing browser cache');
console.log('Grafana reverse-proxy navigation: 11 checks passed');

'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const js=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
const begin=js.indexOf('function durationFmt089(seconds)');
const end=js.indexOf('function trendSvg084(',begin);
assert(begin>=0 && end>begin,'Uptime formatter missing');
const ctx={};
vm.createContext(ctx);
vm.runInContext(js.slice(begin,end),ctx);
const format=ctx.durationFmt089;
for(const [seconds,expected] of [
  [0,'0m'],[59,'0m'],[60,'1m'],[14399,'3h 59m'],
  [14639,'4h 3m'],[86399,'23h 59m'],[86400,'1d'],
  [172800,'2d'],[198900,'2d 7h 15m'],[-1,'—'],[NaN,'—'],[Infinity,'—'],[null,'—']
])assert.equal(format(seconds),expected,'Uptime formatting for '+String(seconds));
assert.match(js,/\$\('trend-uptime'\)\.textContent=durationFmt089\(d\.latest\?\.uptime_secs\)/);
assert.match(js,/keys\[0\]==='uptime_secs'\?durationFmt089/, 'Uptime plot must show duration ticks');
assert.match(html,/Radio uptime · days, hours, minutes/);
assert.match(html,/app\.js\?v=089/);
console.log('0.8.9 radio uptime duration: 17 checks passed');

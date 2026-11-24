'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');

const html = fs.readFileSync('static/index.html', 'utf8');
const js = fs.readFileSync('static/app.js', 'utf8');
const api = fs.readFileSync('station/web.py', 'utf8');

const saveStart = js.indexOf("$('channel-form').addEventListener('submit',");
const saveEnd = js.indexOf("$('channel-delete-form').addEventListener", saveStart);
assert(saveStart >= 0 && saveEnd > saveStart, 'Channel save handler must exist');
const saveHandler = js.slice(saveStart, saveEnd);

assert.match(html, /id="channel-form"/, 'Channel form must remain present');
assert.doesNotMatch(html, /id="channel-confirm"/, 'No typed confirmation input for saving');
assert.doesNotMatch(saveHandler, /\bconfirm\s*\(/, 'No browser confirmation when saving');
assert.doesNotMatch(saveHandler, /channel-confirm/, 'No typed confirmation in save request');
assert.match(saveHandler, /method:'PUT'/, 'Save uses the existing channel PUT endpoint');
assert.match(saveHandler, /await pollCommand\(x\.id\)/, 'Save waits for radio command result');
assert.match(saveHandler, /channelSaveStatus\(err\.message,true\)/, 'Save errors display inline');
assert.match(saveHandler, /!configured && !secret && !name\.startsWith\('#'\)/, 'Hashtag channels may leave the key blank');
assert.match(html, /id="channel-save-status"/, 'Inline save status is available');
assert.match(html, /app\.js\?v=088-channel-save-1/, 'Browser cache is invalidated');
assert.doesNotMatch(api, /body\.confirm != 'SAVE CHANNEL'/, 'Server no longer demands typed confirmation');
assert.match(api, /class ChannelUpdate\(BaseModel\):\s+name:.*\s+secret_hex: str \| None = None/, 'API still accepts channel name and optional key');
assert.match(api, /body\.confirm != f'DELETE CHANNEL \{index\}'/, 'Delete confirmation remains protected');
assert.match(js, /Permanently erase channel/, 'Delete dialog remains protected');

console.log('Channel save UX: 14 checks passed');

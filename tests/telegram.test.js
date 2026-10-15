const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
test('Telegram parser exists', () => assert.ok(fs.existsSync('lib/telegram.js')));
if (fs.existsSync('lib/telegram.js')) {
  const { parseUpdate } = require('../lib/telegram');
  const message = text => ({update_id:123,message:{text,from:{id:42},chat:{id:42,type:'private'}}});
  const uuid='a9c76d53-cbd2-448f-82ed-a07408454bd3';
  test('only owner private chat may issue commands', () => {
    assert.equal(parseUpdate(message('/stop'),42).command,'stop');
    assert.equal(parseUpdate(message('/stop'),43).ignored,true);
    const group=message('/stop'); group.message.chat.type='group';
    assert.equal(parseUpdate(group,42).ignored,true);
    assert.equal(parseUpdate(message('/stop'),null).ignored,true);
  });
  test('inline approval preserves explicit draft version', () => {
    const update={update_id:124,callback_query:{id:'cb1',from:{id:42},data:`a:${uuid}:3`,
      message:{chat:{id:42,type:'private'}}}};
    const command=parseUpdate(update,42);
    assert.equal(command.command,'approve'); assert.equal(command.lead_id,uuid);
    assert.equal(command.version,3); assert.equal(command.callback_id,'cb1');
  });
  test('edit command preserves text as data and rejects malformed identifiers', () => {
    const parsed=parseUpdate(message(`/draft ${uuid} Новый текст; DROP TABLE leads;`),42);
    assert.equal(parsed.draft,'Новый текст; DROP TABLE leads;');
    assert.equal(parseUpdate(message('/approve malicious-id'),42).command,'help');
    assert.equal(parseUpdate({update_id:12},42).ignored,true);
    assert.equal(parseUpdate(message('привет'),42).command,'help');
  });
  test('versionless approval cannot approve the current unreviewed draft',()=>{
    assert.equal(parseUpdate(message(`/approve ${uuid}`),42).command,'help');
    assert.equal(parseUpdate(message(`/approve ${uuid} 3`),42).version,3);
  });
}

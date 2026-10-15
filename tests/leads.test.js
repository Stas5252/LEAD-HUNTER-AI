const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

test('normalization and card modules exist', () => {
  assert.ok(fs.existsSync('lib/leads.js'), 'missing normalization module');
  assert.ok(fs.existsSync('lib/cards.js'), 'missing card module');
});

if (fs.existsSync('lib/leads.js') && fs.existsSync('lib/cards.js')) {
  const { normalizeLead, scoreLead } = require('../lib/leads');
  const { renderCard } = require('../lib/cards');
  const raw = {
    company_name: 'DEMO мебель N', city: 'Самара', niche: 'мебель', source: 'fixture',
    source_type: 'maps_demo', source_url: 'https://example.invalid/request/1?utm_source=test',
    text: 'Ищем разработчика: нужен интернет-магазин с каталогом мебели.',
    is_demo: true, published_at: '2026-10-15T06:00:00Z'
  };
  test('normalizer runs inside a restricted n8n-like VM without a global URL', () => {
    const vm = require('node:vm');
    const scope = { module: { exports: {} }, require };
    vm.runInNewContext(fs.readFileSync('lib/leads.js', 'utf8'), scope);
    assert.equal(scope.module.exports.normalizeLead(raw).company_name, raw.company_name);
  });
  test('fresh direct request has evidence and high score', () => {
    const lead = scoreLead(normalizeLead(raw), { now: '2026-10-15T12:00:00Z' });
    assert.equal(lead.classification, 'DIRECT_REQUEST');
    assert.ok(lead.score_0_100 >= 90);
    assert.equal(lead.proof_quote, raw.text);
    assert.equal(lead.website_status, 'UNKNOWN');
    assert.equal(lead.scoring_method, 'heuristic');
  });
  test('offers from developers and staff vacancies are not customer requests', () => {
    const offer = scoreLead(normalizeLead({ ...raw, text: 'Делаю сайты и ботов. Заказывайте у меня!' }));
    assert.equal(offer.classification, 'COMPETITOR');
    const vacancy = scoreLead(normalizeLead({ ...raw, text: 'Ищем разработчика в штат, полная занятость.' }));
    assert.equal(vacancy.classification, 'IRRELEVANT');
    const spam = scoreLead(normalizeLead({ ...raw, text: 'Казино, заработок без вложений!' }));
    assert.equal(spam.classification, 'IRRELEVANT');
  });
  test('no website field or unverified absence is UNKNOWN', () => {
    assert.equal(normalizeLead({ ...raw, website_status: 'ABSENT_CONFIRMED' }).website_status, 'UNKNOWN');
    assert.equal(normalizeLead({ ...raw, website: 'https://example.invalid' }).website_status, 'UNVERIFIED');
  });
  test('tracking URL differences deduplicate; different social profiles do not', () => {
    const a = normalizeLead(raw);
    const b = normalizeLead({ ...raw, source_url: 'https://example.invalid/request/1?utm_medium=demo#fragment' });
    assert.equal(a.dedupe_key, b.dedupe_key);
    const c = normalizeLead({ ...raw, source_url: 'https://t.me/a/1', website: 'https://vk.com/shop1' });
    const d = normalizeLead({ ...raw, source_url: 'https://t.me/b/1', website: 'https://vk.com/shop2' });
    assert.notEqual(c.dedupe_key, d.dedupe_key);
  });
  test('shared directory listings and mobile social profiles cannot merge different companies', () => {
    const listing={...raw,source_url:'https://directory.example/catalog',website:undefined};
    assert.notEqual(normalizeLead({...listing,company_name:'Компания A'}).dedupe_key,
      normalizeLead({...listing,company_name:'Компания B'}).dedupe_key);
    assert.notEqual(normalizeLead({...listing,city:'Самара'}).dedupe_key,
      normalizeLead({...listing,city:'Казань'}).dedupe_key);
    const a=normalizeLead({...listing,source_url:'https://directory.example/a',website:'https://m.vk.com/company_a'});
    const b=normalizeLead({...listing,source_url:'https://directory.example/b',website:'https://m.vk.com/company_b'});
    assert.notEqual(a.dedupe_key,b.dedupe_key);
    assert.equal(normalizeLead(listing).identity_review,true);
    assert.equal(scoreLead(normalizeLead(listing)).status,'REVIEW');
  });
  test('DEMO and real input never share identity; contact changes invalidate content hash', () => {
    const a=normalizeLead({...raw,external_id:'company-1',public_contact:'+79991112233'});
    const b=normalizeLead({...raw,external_id:'company-1',is_demo:false,public_contact:'+79991112233'});
    assert.notEqual(a.dedupe_key,b.dedupe_key);
    assert.notEqual(a.content_hash,normalizeLead({...raw,external_id:'company-1',public_contact:'+79994445566'}).content_hash);
  });
  test('telephone normalization does not invent country code for ten digits', () => {
    assert.equal(normalizeLead({ ...raw, public_contact: '8 (999) 111-22-33' }).public_contact, '+79991112233');
    assert.equal(normalizeLead({ ...raw, public_contact: '9991112233' }).public_contact, '9991112233');
  });
  test('invalid input is rejected and text cannot smuggle active links', () => {
    assert.throws(() => normalizeLead({ ...raw, source_url: 'javascript:alert(1)' }));
    assert.throws(() => normalizeLead({ ...raw, company_name: '' }));
    assert.throws(() => normalizeLead({ ...raw, text: 'x'.repeat(20001) }));
    assert.throws(() => normalizeLead({ ...raw, is_demo: 'false' }));
  });
  test('card labels fixtures, escapes HTML, offers concrete action buttons', () => {
    const lead = { ...scoreLead(normalizeLead({ ...raw, company_name: '<script>DEMO</script>' })),
      lead_id: '29c8bc61-b501-45a3-bb34-89be76872c94', draft_version: 1 };
    const card = renderCard(lead);
    assert.match(card.text, /DEMO: вымышленный пример/);
    assert.ok(!card.text.includes('<script>'));
    assert.match(card.text, /UNKNOWN/);
    assert.match(card.text, /Ищем разработчика/);
    assert.ok(card.reply_markup.inline_keyboard.flat().some(x => x.callback_data?.startsWith('a:')));
    assert.ok(card.reply_markup.inline_keyboard.flat().every(x => !x.callback_data || x.callback_data.length <= 64));
  });
  test('old or undated request cannot claim fresh top priority', () => {
    const old = scoreLead(normalizeLead({ ...raw, published_at: '2020-01-01T00:00:00Z' }));
    const unknown = scoreLead(normalizeLead({ ...raw, published_at: undefined }));
    assert.ok(old.score_0_100 < 90);
    assert.ok(unknown.score_0_100 < 90);
  });
}

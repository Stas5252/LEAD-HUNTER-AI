'use strict';const test=require('node:test'),assert=require('node:assert/strict');const {normalizeLead,scoreLead}=require('../lib/leads');
for(const [need,offer] of [['Нужен специалист по Яндекс Директ','Маркетинг'],['Ищу внедрение CRM','CRM'],['Нужна лидогенерация на звонках','звонк'],['Нужно построение отдела продаж','продаж'],['Нужен рекламный ИИ ролик','ИИ']]){
 test('service demand: '+need,()=>{const r=scoreLead(normalizeLead({company_name:'Клиент',source:'test',source_url:'https://example.org/post/1',proof_quote:need,published_at:new Date().toISOString(),attribution:{utm_campaign:'owner'}}));assert.equal(r.classification,'DIRECT_REQUEST');assert.ok(r.offer_type.includes(offer));assert.equal(r.attribution.utm_campaign,'owner');});
}

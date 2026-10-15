'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const {normalizeLead,scoreLead}=require('../lib/leads');
const raw=()=>({source:'telegram_inbound',source_type:'website_forms',source_url:'https://t.me/LeadMagnetic67_bot?start=web_general',external_id:'visitor:test',company_name:'Заявка',proof_quote:'Хочу обсудить задачу для моего бизнеса',public_contact:'@visitor_test',published_at:new Date().toISOString(),attribution:{intake:'telegram_inbound',consent:true}});
test('consented inbound request reaches owner without keyword guessing or altered quote',()=>{const r=raw(),lead=scoreLead(normalizeLead(r));assert.equal(lead.classification,'DIRECT_REQUEST');assert.equal(lead.score_0_100,95);assert.equal(lead.proof_quote,r.proof_quote);});
test('unconsented and other-source metadata cannot masquerade as inbound request',()=>{for(const change of [{source:'maps'},{source_type:'maps'},{attribution:{intake:'telegram_inbound',consent:false}}])assert.ok(scoreLead(normalizeLead({...raw(),...change})).score_0_100<40);});

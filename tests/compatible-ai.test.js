'use strict';const test=require('node:test'),assert=require('node:assert/strict');const scoring=require('../lib/scoring');
const lead={company_name:'Тест',niche:'маркетинг',city:'Москва',source_url:'https://example.org/post/1',proof_quote:'Нужен Яндекс Директ',content_hash:'same'};
test('compatible chat API uses strict schema and grounded validation',()=>{
 const body=scoring.buildRequest(lead,'provider-model','chat_completions');
 assert.ok(Array.isArray(body.messages),'compatible API needs messages');assert.equal(body.response_format.type,'json_schema');
 const assessment={score_0_100:80,confidence_0_1:.8,classification:'DIRECT_REQUEST',why_relevant:'Запрос',proof_quote:'Нужен Яндекс Директ',offer_type:'Маркетинг',draft_message:'Уточним задачу'};
 const raw={choices:[{finish_reason:'stop',message:{content:JSON.stringify(assessment)}}]};
 assert.equal(scoring.validateScoreResponse(raw,lead).score_0_100,80);
 assert.throws(()=>scoring.validateScoreResponse({choices:[{finish_reason:'length',message:{content:'{}'}}]},lead));
});
test('cache must distinguish provider origins',()=>{assert.notEqual(scoring.cacheKey(lead,'model',false,'provider-a'),scoring.cacheKey(lead,'model',false,'provider-b'));});
test('chat JSON schema uses provider contract without a nested type discriminator',()=>{const r=scoring.buildRequest(lead,'model','chat_completions');assert.equal(r.response_format.json_schema.type,undefined);assert.equal(r.response_format.json_schema.name,'lead_score');});

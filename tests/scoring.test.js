const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
test('Responses API adapter exists',()=>assert.ok(fs.existsSync('lib/scoring.js')));
if(fs.existsSync('lib/scoring.js')) {
  const {buildRequest,validateScoreResponse,cacheKey,applyAssessment}=require('../lib/scoring');
  const lead={proof_quote:'Нужен сайт для кафе',content_hash:'abc',is_demo:true};
  const score={score_0_100:92,confidence_0_1:0.9,classification:'DIRECT_REQUEST',why_relevant:'Прямой запрос',
    proof_quote:'Нужен сайт',offer_type:'Сайт кафе',draft_message:'Здравствуйте! Обсудим сайт для кафе?'};
  const response=value=>({status:'completed',output:[{type:'message',content:[{type:'output_text',text:JSON.stringify(value)}]}]});
  test('request uses Responses JSON Schema, bounded output and no tools',()=>{
    const req=buildRequest(lead,'gpt-4.1-mini');
    assert.equal(req.text.format.type,'json_schema');assert.equal(req.text.format.strict,true);
    assert.equal(req.max_output_tokens,600);assert.equal(req.store,false);assert.equal(req.tools,undefined);
  });
  test('accepts structured output grounded in source quotation',()=>{
    assert.equal(validateScoreResponse(response(score),lead).score_0_100,92);
  });
  test('rejects malformed JSON, refusal, fabricated quotation and invalid ranges',()=>{
    assert.throws(()=>validateScoreResponse({status:'completed',output:[{type:'message',content:[{type:'output_text',text:'oops'}]}]},lead));
    assert.throws(()=>validateScoreResponse({status:'incomplete',output:[]},lead));
    assert.throws(()=>validateScoreResponse(response({...score,score_0_100:101}),lead));
    assert.throws(()=>validateScoreResponse(response({...score,confidence_0_1:2}),lead));
    assert.throws(()=>validateScoreResponse(response({...score,proof_quote:'Бизнес без сайта'}),lead));
    assert.throws(()=>validateScoreResponse(response({...score,extra:'unexpected'}),lead));
  });
  test('cache separates model, schema and mocks',()=>{
    assert.notEqual(cacheKey(lead,'a',false),cacheKey(lead,'b',false));
    assert.notEqual(cacheKey(lead,'a',false),cacheKey(lead,'a',true));
  });
  test('freshness and identity rules apply after both live and cached AI scoring',()=>{
    const source={...lead,published_at:'2026-10-15T00:00:00Z'};
    const assessment={...score,score_0_100:95,why_relevant:'Прямой свежий запрос',scoring_method:'openai'};
    assert.equal(applyAssessment(source,assessment,{now:'2026-10-15T12:00:00Z'}).score_0_100,95);
    const old=applyAssessment(source,assessment,{now:'2026-11-15T00:00:00Z'});
    assert.ok(old.score_0_100<90);
    assert.doesNotMatch(old.why_relevant,/Прямой свежий запрос/);
    const unclear=applyAssessment({...source,identity_review:true},assessment,{now:'2026-10-15T12:00:00Z'});
    assert.equal(unclear.status,'REVIEW');assert.ok(unclear.score_0_100<70);
    const body=buildRequest(source,'gpt-4.1-mini');
    assert.equal(JSON.parse(body.input).published_at,source.published_at);
    assert.notEqual(cacheKey(source,'a'),cacheKey({...source,published_at:'2026-10-01T00:00:00Z'},'a'));
  });
}

#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const root = path.resolve(__dirname, '..');
const read = p => fs.readFileSync(path.join(root, p), 'utf8');
const fixture = JSON.parse(read('fixtures/leads.json'));
const bundle = name => `const ${name} = (()=>{const module={exports:{}};\n${read('lib/' + name + '.js')}\nreturn module.exports;})();\n`;
const id = name => createHash('sha256').update(name).digest('hex').slice(0,32);
function node(name,type,parameters,position,extra={}) {
  return {id:id(name),name,type:'n8n-nodes-base.'+type,typeVersion:type==='code'?2:type==='postgres'?2.6:1,
    parameters,position,...extra};
}
function pg(name,query,params,position) {
  return node(name,'postgres',{operation:'executeQuery',query,options:{queryReplacement:params}},position,
    {credentials:{postgres:{id:'lh-postgres',name:'LEAD HUNTER PostgreSQL'}}});
}
function flow(flowId,name,nodes,edges) {
  const connections={};
  for(const [from,to,port=0] of edges) {
    connections[from]??={main:[[]]};
    while(connections[from].main.length<=port)connections[from].main.push([]);
    connections[from].main[port].push({node:to,type:'main',index:0});
  }
  return {id:flowId,name,active:false,nodes,connections,
    settings:{executionOrder:'v1',saveDataSuccessExecution:'none',saveDataErrorExecution:'all',executionTimeout:120},
    pinData:{},versionId:id(flowId)};
}
function write(file,data){fs.writeFileSync(path.join(root,'workflows',file),JSON.stringify(data,null,2)+'\n');}
function buildImport() {
  const nodes=[
    node('Manual','manualTrigger',{},[0,0]),
    node('Every minute','scheduleTrigger',{rule:{interval:[{field:'minutes',minutesInterval:1}]}},[0,180],{typeVersion:1.2}),
    pg('Load request','SELECT * FROM claim_import(NULL);','',[240,0]),
    pg('Load queued request','SELECT * FROM claim_import(NULL);','',[240,180]),
    node('Normalize and score','code',{jsCode:bundle('leads')+`
const input=$input.first().json;
if(!Array.isArray(input.payload)||input.payload.length>input.max_leads) throw new Error('Неверный ввод или превышен MAX_LEADS_PER_RUN');
const batch=input.payload.map(raw=>leads.scoreLead(leads.normalizeLead(raw)));
if(!batch.length)throw new Error('Пустая выборка: уточните фильтры');
return batch.map(lead=>({json:{request_id:input.request_id,lead}}));`},[480,0]),
    node('Optional AI score','executeWorkflow',{source:'database',workflowId:{__rl:true,value:'lh-openai-score',mode:'id'},mode:'each',options:{waitForSubWorkflow:true}},[600,0],{typeVersion:1.2}),
    node('Collect batch','code',{jsCode:`const items=$input.all();return [{json:{request_id:items[0].json.request_id,batch:items.map(i=>i.json.lead)}}];`},[660,0]),
    pg('Store leads','SELECT complete_import($1::uuid,$2::jsonb) AS result;','={{ [$json.request_id,JSON.stringify($json.batch)] }}',[720,0]),
    node('Cards','code',{jsCode:bundle('cards')+`
const result=$input.first().json.result;
return [{json:{...result,cards:result.leads.map(cards.renderCard)}}];`},[960,0]),
    pg('Save result',"UPDATE import_requests SET result=$2::jsonb,state='DONE',updated_at=now() WHERE request_id=$1::uuid AND state='STORED' RETURNING result;",'={{ [$json.request_id,JSON.stringify($json)] }}',[1200,0]),
  ];
  const result=flow('lh-lead-import','LEAD HUNTER · DEMO / import',nodes,
    [['Manual','Load request'],['Every minute','Load queued request'],['Load request','Normalize and score'],['Load queued request','Normalize and score'],['Normalize and score','Optional AI score'],['Optional AI score','Collect batch'],['Collect batch','Store leads'],['Store leads','Cards'],['Cards','Save result']]);
  result.settings.executionTimeout=1800;
  write('01-lead-import.json',result);
}
function buildScoring() {
  const nodes=[node('Score input','executeWorkflowTrigger',{inputSource:'passthrough'},[0,0],{typeVersion:1.1}),
    pg('Score configuration','SELECT $1::jsonb AS input,to_jsonb(llm_settings) AS config FROM llm_settings WHERE id=true;','={{ [JSON.stringify($json)] }}',[200,0]),
    node('Build Responses request','code',{jsCode:bundle('scoring')+`
const {input,config}=$input.first().json;
const body=scoring.buildRequest(input.lead,config.model,config.api_style);
const bytes=Buffer.byteLength(JSON.stringify(body),'utf8')+2048;
return [{json:{input,body,max_input_tokens:bytes,key:scoring.cacheKey(input.lead,config.model,config.mock_mode,config.endpoint+'|'+config.api_style)}}];`},[400,0]),
    pg('Reserve score','SELECT reserve_score($1::jsonb,$2::text,$3::integer,$4::jsonb) AS decision;','={{ [JSON.stringify($json.input),$json.key,$json.max_input_tokens,JSON.stringify($json.body)] }}',[600,0]),
    node('Call allowed','if',{conditions:{options:{caseSensitive:true,leftValue:'',typeValidation:'strict',version:2},
      conditions:[{id:id('call-condition'),leftValue:'={{ $json.decision.mode }}',rightValue:'CALL',operator:{type:'string',operation:'equals'}}],combinator:'and'},options:{}},[800,0],{typeVersion:2.2}),
    node('Responses API','httpRequest',{method:'POST',url:'={{ $json.decision.endpoint }}',authentication:'genericCredentialType',genericAuthType:'httpHeaderAuth',
      sendBody:true,specifyBody:'json',jsonBody:'={{ JSON.stringify($json.decision.request_body) }}',options:{timeout:20000,response:{response:{fullResponse:true,neverError:true,responseFormat:'json'}}}},[1000,-100],
      {typeVersion:4.2,credentials:{httpHeaderAuth:{id:'lh-openai',name:'LEAD HUNTER OpenAI'}},onError:'continueRegularOutput',retryOnFail:false}),
    node('Validate AI output','code',{jsCode:bundle('scoring')+`
const decision=$('Reserve score').first().json.decision;
let assessment=null;try{const r=$input.first().json;if(!r.error&&(!r.statusCode||r.statusCode===200))assessment=scoring.validateScoreResponse(r.body||r,decision.lead);}catch(e){}
return [{json:{decision,assessment}}];`},[1200,-100]),
    pg('Cache valid score','SELECT finish_score($1::jsonb,$2::jsonb) AS output;','={{ [JSON.stringify($json.decision),JSON.stringify($json.assessment)] }}',[1400,-100]),
    node('AI result','code',{jsCode:bundle('scoring')+`const r=$input.first().json.output;return [{json:{...r,lead:scoring.applyAssessment(r.lead,{})}}];`},[1600,-100]),
    node('Heuristic or cached result','code',{jsCode:bundle('scoring')+`const d=$input.first().json.decision;return [{json:{request_id:d.request_id,lead:scoring.applyAssessment(d.lead,d.mode==='CACHE'?d.cached:{})}}];`},[1000,100])];
  write('04-openai-score.json',flow('lh-openai-score','LEAD HUNTER · Optional Responses scoring',nodes,
    [['Score input','Score configuration'],['Score configuration','Build Responses request'],['Build Responses request','Reserve score'],['Reserve score','Call allowed'],['Call allowed','Responses API',0],['Call allowed','Heuristic or cached result',1],['Responses API','Validate AI output'],['Validate AI output','Cache valid score'],['Cache valid score','AI result']]));
}
function webhook(name,url,pos) {
  return node(name,'webhook',{httpMethod:'POST',path:url,authentication:'headerAuth',responseMode:'responseNode',options:{}},pos,
    {typeVersion:2,webhookId:id(url),credentials:{httpHeaderAuth:{id:'lh-webhook',name:'LEAD HUNTER local webhook'}}});
}
function response(name,pos) {
  return node(name,'respondToWebhook',{respondWith:'json',responseBody:'={{ $json.result }}',options:{}},pos,{typeVersion:1.4});
}
function buildTelegram() {
  const nodes=[webhook('Telegram update','lh-telegram',[0,0]),
    pg('Owner context','SELECT $1::jsonb AS payload,admin_id,monitor_update($1::jsonb) AS monitoring,visitor_update($1::jsonb) AS visitor FROM app_settings WHERE id=true;','={{ [JSON.stringify($json.body)] }}',[240,0]),
    node('Authorize and parse','code',{jsCode:bundle('telegram')+`const input=$input.first().json;return [{json:{command:telegram.parseUpdate(input.payload,input.admin_id),visitor:input.visitor}}];`},[480,0]),
    pg('Apply command',"SELECT CASE WHEN coalesce(($2::jsonb->>'handled')::boolean,false) THEN $2::jsonb->'result' ELSE handle_command($1::jsonb) END AS result;",'={{ [JSON.stringify($json.command),JSON.stringify($json.visitor||{})] }}',[720,0]),
    node('Format replies','code',{jsCode:bundle('cards')+`
const r=$input.first().json.result;
const messages=r.ignored?[]:[...(r.text?[{text:cards.escapeHtml(r.text),parse_mode:'HTML',...(r.reply_markup?{reply_markup:r.reply_markup}:{})}]:[]),...(r.leads||[]).map(cards.renderCard)];
if(!r.ignored&&r.callback_id)messages.unshift({_method:'answerCallbackQuery',callback_query_id:r.callback_id,text:'Принято'});
return [{json:{update_id:r.update_id||null,messages,callback_id:r.callback_id||null}}];`},[960,0]),
    pg('Queue command replies',"SELECT queue_replies($1::bigint,$2::jsonb)||jsonb_build_object('callback_id',$3::text) AS result;",'={{ [$json.update_id,JSON.stringify($json.messages),$json.callback_id] }}',[1200,0]),
    response('Command accepted',[1440,0])];
  write('02-telegram.json',flow('lh-telegram','LEAD HUNTER · Telegram commands',nodes,
    [['Telegram update','Owner context'],['Owner context','Authorize and parse'],['Authorize and parse','Apply command'],['Apply command','Format replies'],['Format replies','Queue command replies'],['Queue command replies','Command accepted']]));
  const transport=[webhook('Transport request','lh-transport',[0,0]),
    pg('Transport state','SELECT transport_action($1::jsonb) AS result;','={{ [JSON.stringify($json.body)] }}',[240,0]),
    node('Render notifications','code',{jsCode:bundle('cards')+`
const r=$input.first().json.result;
if(r.jobs)r.jobs=r.jobs.map(j=>({id:j.id,message:{...(['message','media_preview','visitor_reply'].includes(j.payload.type)?j.payload.data:cards.renderCard(j.payload)),chat_id:j.chat_id}}));
return [{json:{result:r}}];`},[480,0]),response('Transport response',[720,0])];
  write('03-notifications.json',flow('lh-transport','LEAD HUNTER · Notification outbox',transport,
    [['Transport request','Transport state'],['Transport state','Render notifications'],['Render notifications','Transport response']]));
}
buildImport();
buildTelegram();
buildScoring();
module.exports={node,pg,flow,write,bundle,fixture};

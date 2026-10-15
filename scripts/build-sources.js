'use strict';
const {node,pg,flow,write,bundle}=require('./build-workflows');
const kinds=['maps','new_business','telegram_monitor','audit','niche','subcontract','website_forms','partners','content','threads_search'];
for(const [i,kind] of kinds.entries()){
 const nodes=[node('Manual','manualTrigger',{},[0,0]),node('Hourly','scheduleTrigger',{rule:{interval:[{field:'hours',hoursInterval:1}]}},[0,160],{typeVersion:1.2}),pg('Enqueue configured source',`SELECT enqueue_configured('${kind}') AS result;`,'',[240,0])];
 write(`${10+i}-${kind}.json`,flow('lh-source-'+kind,'LEAD HUNTER · '+kind,nodes,[['Manual','Enqueue configured source'],['Hourly','Enqueue configured source']]));
}
function hook(name,path){return node(name,'webhook',{httpMethod:'POST',path,authentication:'headerAuth',responseMode:'responseNode',options:{}},[0,0],{typeVersion:2,webhookId:path,credentials:{httpHeaderAuth:{id:'lh-webhook',name:'LEAD HUNTER local webhook'}}});}
function respond(){return node('Response','respondToWebhook',{respondWith:'json',responseBody:'={{ $json.result }}',options:{}},[720,0],{typeVersion:1.4});}
write('20-worker.json',flow('lh-worker','LEAD HUNTER · Source worker transport',[hook('Worker','lh-worker'),pg('Queue action','SELECT connector_action($1::jsonb) AS result;','={{ [JSON.stringify($json.body)] }}',[240,0]),respond()],[['Worker','Queue action'],['Queue action','Response']]));
write('21-form.json',flow('lh-form','LEAD HUNTER · Signed website form',[
 node('Form','webhook',{httpMethod:'POST',path:'lh-form',authentication:'headerAuth',responseMode:'responseNode',options:{}},[0,0],{typeVersion:2,webhookId:'lh-form',credentials:{httpHeaderAuth:{id:'lh-form-key',name:'LEAD HUNTER server form key'}}}),
 node('Validate form','code',{jsCode:bundle('forms')+`const r=$input.first().json;return [{json:forms.parseForm(r.body,r.headers['x-lh-signature'])}];`},[240,0]),
 pg('Accept signed form','SELECT receive_form($1::jsonb) AS result;','={{ [JSON.stringify($json)] }}',[480,0]),respond()],
 [['Form','Validate form'],['Validate form','Accept signed form'],['Accept signed form','Response']]));
write('22-reminders.json',flow('lh-reminders','LEAD HUNTER · CRM reminders',[node('Every five minutes','scheduleTrigger',{rule:{interval:[{field:'minutes',minutesInterval:5}]}},[0,0],{typeVersion:1.2}),pg('Queue reminders','SELECT queue_reminders() AS result;','',[240,0])],[['Every five minutes','Queue reminders']]));

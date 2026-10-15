'use strict';
const {node,pg,flow,write}=require('./build-workflows');
for(const [name,fn] of [['content','content_action'],['media','media_action']]){
 const nodes=[node('Worker','webhook',{httpMethod:'POST',path:'lh-'+name,authentication:'headerAuth',responseMode:'responseNode',options:{}},[0,0],{typeVersion:2,webhookId:'lh-'+name,credentials:{httpHeaderAuth:{id:'lh-webhook',name:'LEAD HUNTER local webhook'}}}),pg('Action',`SELECT ${fn}($1::jsonb) AS result;`,'={{ [JSON.stringify($json.body)] }}',[240,0]),node('Response','respondToWebhook',{respondWith:'json',responseBody:'={{ $json.result }}',options:{}},[480,0],{typeVersion:1.4})];
 write(name==='content'?'23-content.json':'24-media.json',flow('lh-'+name,'LEAD HUNTER · '+name+' queue',nodes,[['Worker','Action'],['Action','Response']]));
}

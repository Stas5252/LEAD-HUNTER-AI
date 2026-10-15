'use strict';
// Import this project's reproducible definitions and encrypted credentials.
// Full workflow backups precede replacements. No credentials in stdout/argv.
const fs=require('node:fs'),net=require('node:net'),cp=require('node:child_process'),path=require('node:path');
const home='/home/node/.n8n',src='/opt/lead-hunter/workflows';
fs.mkdirSync(home,{recursive:true});
async function wait(){for(let n=0;n<120;n++){if(await new Promise(resolve=>{const s=net.connect({host:process.env.DB_POSTGRESDB_HOST,port:Number(process.env.DB_POSTGRESDB_PORT||5432)});s.setTimeout(1500);s.once('connect',()=>{s.destroy();resolve(true)});s.once('error',()=>resolve(false));s.once('timeout',()=>{s.destroy();resolve(false)})}))return;await new Promise(r=>setTimeout(r,1000))}throw Error('Database readiness timeout')}
function cli(args){const r=cp.spawnSync('n8n',args,{encoding:'utf8'});fs.appendFileSync(home+'/bootstrap.log',(r.stdout||'')+(r.stderr||''),{mode:0o600});if(r.status!==0)throw Error('n8n bootstrap command failed: '+args[0]);}
async function main(){
 await wait();
 const backup=home+'/workflow-backups';fs.mkdirSync(backup,{recursive:true,mode:0o700});
 const stamp=Date.now();cli(['export:workflow','--all','--output='+backup+'/'+stamp+'.json']);
 const credBackup=backup+'/credentials-'+stamp+'.json';cli(['export:credentials','--all','--output='+credBackup]);
 const existingIds=new Set((fs.existsSync(credBackup)?JSON.parse(fs.readFileSync(credBackup,'utf8')):[]).map(c=>c.id));
 const temp=fs.mkdtempSync('/tmp/lh-bootstrap-');
 try{
  const creds=[{id:'lh-postgres',name:'LEAD HUNTER PostgreSQL',type:'postgres',data:{host:process.env.DB_POSTGRESDB_HOST,port:Number(process.env.DB_POSTGRESDB_PORT||5432),database:'lead_hunter',user:'lead_hunter',password:process.env.APP_DB_PASSWORD,ssl:'disable'}},
   {id:'lh-webhook',name:'LEAD HUNTER local webhook',type:'httpHeaderAuth',data:{name:'X-Telegram-Bot-Api-Secret-Token',value:process.env.TELEGRAM_WEBHOOK_SECRET}},
   {id:'lh-form-key',name:'LEAD HUNTER server form key',type:'httpHeaderAuth',data:{name:'X-LH-Form-Key',value:process.env.INGEST_TOKEN}},
   {id:'lh-openai',name:'LEAD HUNTER OpenAI',type:'httpHeaderAuth',data:{name:'Authorization',value:'Bearer DISABLED_NO_CREDENTIALS'}}];
  for(const name of ['APP_DB_PASSWORD','TELEGRAM_WEBHOOK_SECRET','INGEST_TOKEN'])if(!process.env[name])throw Error('Missing required secure setting: '+name);
  fs.writeFileSync(temp+'/credentials.json',JSON.stringify(creds.filter(c=>c.id!=='lh-openai'||!existingIds.has('lh-openai'))),{mode:0o600});cli(['import:credentials','--input='+temp+'/credentials.json']);fs.unlinkSync(temp+'/credentials.json');
  const flows=fs.readdirSync(src).filter(f=>f.endsWith('.json')).sort().map(f=>JSON.parse(fs.readFileSync(path.join(src,f),'utf8')));
  fs.writeFileSync(temp+'/workflows.json',JSON.stringify(flows),{mode:0o600});cli(['import:workflow','--input='+temp+'/workflows.json']);
  for(const f of flows)cli(['publish:workflow','--id='+f.id]);
 }finally{fs.rmSync(temp,{recursive:true,force:true})}
 console.log('LEAD HUNTER workflows imported; starting n8n. External publication requires owner approval.');
 const child=cp.spawn('n8n',['start'],{stdio:'inherit'});for(const sig of ['SIGTERM','SIGINT'])process.on(sig,()=>child.kill(sig));child.on('exit',code=>process.exit(code??1));
}
main().catch(()=>{console.error('Bootstrap failed; inspect private bootstrap.log; secrets suppressed.');process.exit(1)});

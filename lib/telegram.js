'use strict';
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function parseUpdate(update, adminId) {
  const base={update_id: Number.isSafeInteger(update?.update_id) && update.update_id>=0 ? update.update_id : null,ignored:true};
  const cb=update?.callback_query;
  const message=cb?.message||update?.message;
  const user=cb?.from||message?.from;
  if(!base.update_id || !adminId || String(user?.id)!==String(adminId) ||
     String(message?.chat?.id)!==String(adminId) || message?.chat?.type!=='private') return base;
  const result={...base,ignored:false,user_id:user.id,chat_id:message.chat.id,chat_type:'private',callback_id:cb?.id||null};
  if(cb) {
    const parts=String(cb.data||'').split(':');
    if(parts[0]==='f') return {...result,command:'find',args:parts[1]||'maps_demo'};
    if(!UUID.test(parts[1]||'')) return {...result,command:'help'};
    const command={a:'approve',r:'reject',d:'edit'}[parts[0]];
    const version=Number(parts[2]);
    if(!command || (command==='approve'&&(!Number.isInteger(version)||version<1))) return {...result,command:'help'};
    return {...result,command,lead_id:parts[1],version:command==='approve'?version:null};
  }
  const text=String(message.text||'').trim();
  if(text.length>3500) return {...result,command:'help'};
  const match=/^\/([a-z]+)(?:@[a-z0-9_]+)?(?:\s+([\s\S]*))?$/i.exec(text);
  if(!match) return {...result,command:'help'};
  const cmd=match[1].toLowerCase(),args=(match[2]||'').trim();
  if(['lead','draft','approve','reject'].includes(cmd)) {
    const [leadId,...rest]=args.split(/\s+/);
    if(!UUID.test(leadId||'')) return {...result,command:'help'};
    const version=rest[0]===undefined?null:Number(rest[0]);
    if(cmd==='approve' && (!Number.isSafeInteger(version)||version<1)) return {...result,command:'help'};
    return {...result,command:cmd,lead_id:leadId,version:cmd==='approve'?version:null,
      draft:cmd==='draft'?rest.join(' '):null};
  }
  const allowed=['start','today','find','leads','sources','stats','budget','stop','resume','threads','instagram','videos','source','stage','followup','jobs','chats','content','publish','cancel','media'];
  return {...result,command:allowed.includes(cmd)?cmd:'help',args};
}
module.exports={parseUpdate};

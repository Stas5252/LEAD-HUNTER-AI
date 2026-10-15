'use strict';
const {URL}=require('url');
function sorted(value){if(Array.isArray(value))return value.map(sorted);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,sorted(value[k])]));return value;}
function signingInput(body){return JSON.stringify(sorted(body));}
function parseForm(body,signature,{now=Math.floor(Date.now()/1000)}={}){
 if(!body||typeof body!=='object'||Array.isArray(body))throw Error('Invalid form');
 if(body.consent!==true)throw Error('Explicit consent required');
 if(!Number.isSafeInteger(body.timestamp)||Math.abs(now-body.timestamp)>300)throw Error('Invalid timestamp');
 if(!/^[a-zA-Z0-9_-]{12,100}$/.test(body.nonce||''))throw Error('Invalid nonce');
 if(!/^[a-f0-9]{64}$/.test(signature||''))throw Error('Invalid signature');
 if(typeof body.contact!=='string'||body.contact.length<3||body.contact.length>300||typeof body.message!=='string'||body.message.length<3||body.message.length>4000)throw Error('Invalid contact/message');
 const origin=new URL(body.source_url);if(origin.origin!=='https://stanislavweb.ru'||origin.username||origin.password)throw Error('Invalid form origin');
 const input=signingInput(body);if(input.length>8000)throw Error('Form too large');
 return {payload:body,signature,signing_input:input};
}
module.exports={signingInput,parseForm};

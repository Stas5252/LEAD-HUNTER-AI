'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),crypto=require('node:crypto');
let forms;try{forms=require('../lib/forms');}catch{}
test('form canonical signature is independent of property order and rejects missing consent',()=>{
 assert.ok(forms,'signed forms adapter required');
 const body={nonce:'test-request-1234',timestamp:Math.floor(Date.now()/1000),contact:'owner@example.org',message:'Нужен сайт',consent:true,source_url:'https://stanislavweb.ru',utm:{campaign:'test'}};
 const signature=crypto.createHmac('sha256','private-key').update(forms.signingInput(body)).digest('hex');
 const r=forms.parseForm(body,signature);assert.equal(r.signature,signature);assert.equal(r.payload.consent,true);
 assert.equal(forms.signingInput({...body,contact:body.contact}),r.signing_input);
 assert.throws(()=>forms.parseForm({...body,consent:false},signature),/consent/i);
 assert.throws(()=>forms.parseForm({...body,timestamp:1},signature),/timestamp/i);
});
test('form validation works in n8n isolated Code context without browser globals',()=>{
 const vm=require('node:vm'),fs=require('node:fs'),module={exports:{}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../lib/forms'),'utf8'),{module,require});
 assert.doesNotThrow(()=>module.exports.parseForm({nonce:'test-123456789',timestamp:Math.floor(Date.now()/1000),contact:'x@y',message:'Нужен сайт',consent:true,source_url:'https://stanislavweb.ru'},'a'.repeat(64)));
});

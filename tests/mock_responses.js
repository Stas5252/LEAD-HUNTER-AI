'use strict';
const http=require('node:http');
let calls=0,mode='ok';
const server=http.createServer((req,res)=>{
  if(req.url==='/stats'){res.end(JSON.stringify({calls,mode}));return;}
  if(req.url.startsWith('/mode/')){mode=req.url.split('/').pop();res.end('OK');return;}
  if(req.url==='/shutdown'){res.end('OK');server.close();return;}
  let body='';req.on('data',c=>body+=c);req.on('end',()=>{
    calls++;
    if(mode==='rate'){res.writeHead(429,{'Content-Type':'application/json'});res.end(JSON.stringify({error:{message:'TEST rate limit'}}));return;}
    const request=JSON.parse(body),input=JSON.parse(request.input);
    const score={score_0_100:92,confidence_0_1:0.85,classification:'DIRECT_REQUEST',why_relevant:'Тестовый ответ API-мока, не настоящая AI-оценка.',
      proof_quote:input.text.slice(0,12),offer_type:'Сайт для кафе',draft_message:'Здравствуйте! Обсудим вашу задачу по сайту?'};
    const response={status:'completed',output:[{type:'message',content:[{type:'output_text',text:mode==='invalid'?'BROKEN JSON':JSON.stringify(score)}]}]};
    const send=()=>{res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(response));};
    if(mode==='timeout')setTimeout(send,25000);else send();
  });
});
server.listen(9099,'127.0.0.1');

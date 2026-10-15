"""Official API clients. OAuth/channel permissions are managed by Postiz.

Contracts: Meta fbsamples/threads_api 854fc14; Postiz 021c2ee. No POST retries.
"""
from datetime import datetime,timezone,timedelta
import re,json
from pathlib import Path
from urllib.parse import urlsplit,quote
import httpx

class AmbiguousPublish(RuntimeError):pass

class PostizClient:
 def __init__(self,base,key,*,transport=None):
  p=urlsplit(base)
  if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:raise ValueError('Postiz requires trusted HTTPS API URL')
  if not key:raise ValueError('NEEDS_ACCESS: POSTIZ_API_KEY')
  self.base=base.rstrip('/');self.client=httpx.Client(headers={'Authorization':key},timeout=45,follow_redirects=False,transport=transport)
 def request(self,method,path,**kw):
  try:r=self.client.request(method,self.base+path,**kw)
  except httpx.TransportError:
   if method=='POST':raise AmbiguousPublish('Network failure after POST; reconcile before retry') from None
   raise ValueError('Provider network unavailable') from None
  if r.status_code>=500 and method=='POST':raise AmbiguousPublish('Provider 5xx after POST; reconcile before retry')
  if r.status_code>=300:raise ValueError('Provider HTTP '+str(r.status_code))
  try:return r.json()
  except ValueError:
   if method=='POST':raise AmbiguousPublish('Unparseable POST response') from None
   raise ValueError('Invalid provider response') from None
 def integrations(self):return self.request('GET','/integrations')
 def upload(self,path):
  p=Path(path)
  if p.stat().st_size>45_000_000:raise ValueError('Upload size limit')
  with p.open('rb') as f:return self.request('POST','/upload',files={'file':(p.name,f)})
 def publish(self,item,media):
  if item['channel']=='instagram' and not media:raise ValueError('Instagram needs media')
  settings={'__type':item['channel']}
  if item['channel']=='instagram':settings['post_type']='post'
  body={'type':'now','shortLink':False,'date':item['due_at'],'tags':[],
   'posts':[{'integration':{'id':item['integration_id']},'value':[{'content':item['text'],'image':media}], 'settings':settings}]}
  return self.request('POST','/posts',json=body)
 def posts(self,start,end):return self.request('GET','/posts',params={'startDate':start,'endDate':end})
 def analytics(self,integration,date):return self.request('GET','/analytics/'+quote(integration,safe=''),params={'date':date})
 def close(self):self.client.close()

class ThreadsClient:
 def __init__(self,token,*,review_confirmed=False,transport=None):
  self.token=token;self.review=review_confirmed
  self.client=httpx.Client(timeout=25,follow_redirects=False,transport=transport,headers={'Authorization':'Bearer '+token})
 def get(self,path,params):
  if not self.token:raise ValueError('NEEDS_ACCESS: THREADS_ACCESS_TOKEN')
  try:r=self.client.get('https://graph.threads.com/v1.0/'+path,params=params)
  except httpx.HTTPError:raise ValueError('Threads network unavailable') from None
  if r.status_code>=300:raise ValueError('Threads HTTP '+str(r.status_code))
  return r.json()
 def search(self,query,after=None,max_age_days=7):
  if not self.review:raise ValueError('NEEDS_APP_REVIEW: threads_keyword_search')
  if not query or len(query)>200:raise ValueError('Query length')
  params={'q':query,'search_type':'RECENT','fields':'id,username,text,timestamp,permalink','limit':50}
  if after:
   if len(after)>2000:raise ValueError('Cursor limit')
   params['after']=after
  result=self.get('keyword_search',params);rows=[];now=datetime.now(timezone.utc)
  for d in result.get('data',[])[:100]:
   text=d.get('text','');stamp=d.get('timestamp');link=d.get('permalink','')
   if not re.search('[а-яё]',text,re.I) or not stamp or not link:continue
   try:age=now-datetime.fromisoformat(stamp.replace('Z','+00:00'))
   except (ValueError,TypeError):continue
   if not timedelta(0)<=age<=timedelta(days=max_age_days):continue
   rows.append({'source':'threads_search','source_type':'threads_search','source_url':link,'external_id':'threads:'+str(d['id']),
    'company_name':d.get('username','Threads запрос'),'proof_quote':text[:12000],'published_at':stamp,'is_demo':False})
  # Never follow paging.next: it can carry a token or an attacker-controlled origin.
  return rows,result.get('paging',{}).get('cursors',{}).get('after')
 def own_replies(self,thread_id):
  if not re.fullmatch(r'[0-9]+',thread_id):raise ValueError('Invalid thread ID')
  return self.get(thread_id+'/replies',{'fields':'id,text,timestamp,permalink,username','limit':50})
 def close(self):self.client.close()

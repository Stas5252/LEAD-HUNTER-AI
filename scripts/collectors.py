"""Source adapters produce evidence, never fabricate demand or missing websites."""
from datetime import datetime,timezone
import json,re
from urllib.parse import urlencode,urlsplit
import feedparser
from bs4 import BeautifulSoup
from safe_http import site_fetch,provider_fetch
from site_audit import audit

KINDS=('maps','new_business','telegram_monitor','audit','niche','subcontract','website_forms','partners','content','threads_search')
REQUEST=re.compile(r'нуж[её]н|нужна|ищ[уе]|требуется|ищем|looking for|need a|seeking|подряд|партн[её]р',re.I)
OFFER=re.compile(r'предлага[юе]|разрабатываем|we build|наши услуги|в штат|full.?time',re.I)

def base(kind,row):
    d=dict(row);d.update(source_type=kind,source=d.get('source') or kind,is_demo=d.get('is_demo') is True)
    d.setdefault('company_name','Публичный запрос');d.setdefault('website_status','UNKNOWN')
    d.setdefault('proof_quote','');d.setdefault('observed_at',datetime.now(timezone.utc).isoformat())
    if not d.get('source_url') or urlsplit(d['source_url']).scheme not in ('http','https'):raise ValueError('Public source URL required')
    for key in ('company_name','proof_quote','draft_message'):
        if len(str(d.get(key,'')))>12000:raise ValueError('Text limit')
    return d

def maps(cfg,fetch):
    b=cfg.get('bbox',[]);tag=cfg.get('tag','')
    if len(b)!=4 or not all(isinstance(n,(int,float)) for n in b):raise ValueError('bbox south,west,north,east required')
    s,w,n,e=b
    if not (-90<=s<n<=90 and -180<=w<e<=180 and (n-s)*(e-w)<=4):raise ValueError('Bounding box too large/invalid')
    if not re.fullmatch(r'[a-z_]{1,32}=[a-z_0-9-]{1,64}',tag):raise ValueError('Use one OSM key=value tag')
    key,value=tag.split('=');query=f'[out:json][timeout:20];nwr["{key}"="{value}"]({s},{w},{n},{e});out tags center 100;'
    body=(fetch or provider_fetch)('https://overpass-api.de/api/interpreter',method='POST',data=urlencode({'data':query}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'LeadHunter/1.0 OSM bounded query'})
    rows=[]
    for el in json.loads(body).get('elements',[])[:100]:
        tags=el.get('tags',{});identity=f"{el['type']}:{el['id']}";website=tags.get('website') or tags.get('contact:website')
        rows.append(base('maps',{'external_id':'osm:'+identity,'company_name':tags.get('name','Бизнес OSM'),
            'source_url':f"https://www.openstreetmap.org/{el['type']}/{el['id']}",'website':website,
            'website_status':'PRESENT' if website else 'UNKNOWN','city':cfg.get('city',''),'niche':value,
            'public_contact':tags.get('contact:phone') or tags.get('phone'),
            'proof_quote':'OSM tags: '+json.dumps(tags,ensure_ascii=False)[:1500],
            'attribution':{'provider':'© OpenStreetMap contributors','license':'ODbL','osm_tags':tags}}))
    return rows

def records(kind,cfg):
    raw=cfg.get('records',[])
    if not isinstance(raw,list) or len(raw)>100:raise ValueError('MAX_LEADS_PER_RUN=100')
    rows=[]
    for row in raw:
        if kind=='new_business':
            if not row.get('registration_id') or not row.get('registered_at'):raise ValueError('Registration ID/date required')
            datetime.fromisoformat(row['registered_at'])
            row={**row,'external_id':'registration:'+str(row['registration_id']),'proof_quote':f"Регистрация {row['registration_id']}, дата {row['registered_at']}. Потребность в услугах не подтверждена.",'signal_type':'registration'}
        rows.append(base(kind,row))
    return rows

def feed(kind,cfg,fetch):
    if cfg.get('permission_confirmed') is not True:raise ValueError('Source permission must be confirmed')
    b=(fetch or site_fetch)(cfg['feed_url'])
    if len(b)>2_000_000:raise ValueError('Feed limit')
    f=feedparser.parse(b)
    if f.bozo and not f.entries:raise ValueError('Invalid RSS/Atom')
    result=[]
    for item in f.entries[:100]:
        text=BeautifulSoup(item.get('title','')+' '+item.get('summary',''),'html.parser').get_text(' ',strip=True)[:4000]
        if not REQUEST.search(text) or OFFER.search(text):continue
        stamp=item.get('published_parsed') or item.get('updated_parsed')
        date=datetime(*stamp[:6],tzinfo=timezone.utc).isoformat() if stamp else None
        result.append(base(kind,{'company_name':item.get('author','Публичный запрос'),'source_url':item.get('link',''),
            'external_id':item.get('id') or item.get('link'),'published_at':date,'proof_quote':text,'signal_type':'direct_request' if kind=='subcontract' else 'partner'}))
    return result

def collect(kind,cfg,fetch=None):
    if kind not in KINDS:raise ValueError('Unknown source')
    if kind=='maps':return maps(cfg,fetch)
    if kind=='audit':
        url=cfg['website'];a=audit(url,fetch or site_fetch)
        return [base(kind,{'company_name':cfg.get('company_name',urlsplit(url).hostname),'website':url,'source_url':url,
            'website_status':'PRESENT','proof_quote':'; '.join(v['finding']+' ('+v['evidence']+')' for v in a['findings']),
            'audit':a,'need_detected':'Предложить проверку наблюдений аудита','signal_type':'audit'})]
    if kind=='niche':
        niche=cfg.get('niche','бизнес');name=cfg.get('company_name','Нишевой пример')
        return [base(kind,{**cfg,'company_name':name,'portfolio_url':'https://stanislavweb.ru',
            'draft_message':f'Здравствуйте! Для {name} могу предложить сайт с понятным описанием услуг и формой заявки. Предлагаю сначала уточнить задачу и объём. Мой сайт: https://stanislavweb.ru',
            'proof_quote':cfg.get('proof_quote',f'Подбор шаблона предложения для ниши {niche}; кейс и потребность не подтверждены.')})]
    if cfg.get('feed_url'):return feed(kind,cfg,fetch)
    return records(kind,cfg)

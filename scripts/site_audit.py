"""Observable HTML facts only. No simulated mobile/performance scores."""
from bs4 import BeautifulSoup
from safe_http import site_fetch

def audit_html(url,html):
    if len(html)>2_000_000:raise ValueError('HTML limit')
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style']):tag.decompose()
    checks={'https':url.startswith('https://'),'title':soup.title.get_text(' ',strip=True)[:200] if soup.title else '',
        'description':bool(soup.find('meta',attrs={'name':'description'})),
        'has_viewport':bool(soup.find('meta',attrs={'name':'viewport'})),
        'has_form':bool(soup.find('form')),
        'has_public_contact':bool(soup.select('a[href^="tel:"],a[href^="mailto:"]')),
        'mobile_usability':'NOT_MEASURED','performance':'NOT_MEASURED'}
    labels={'https':'Страница получена по HTTP; HTTPS отдельно не проверен','title':'Не найден title','description':'Не найден meta description',
        'has_viewport':'Не найден viewport; адаптивность требует визуальной проверки',
        'has_form':'В полученном HTML не найдена форма; другие страницы не проверялись',
        'has_public_contact':'В полученном HTML не найдены tel:/mailto: ссылки'}
    return {'url':url,'checks':checks,'findings':[{'finding':label,'evidence':f'HTML наблюдение: {key}=false','source_url':url} for key,label in labels.items() if not checks[key]]}

def audit(url,fetch=site_fetch):return audit_html(url,fetch(url))

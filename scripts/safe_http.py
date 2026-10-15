"""Bounded HTTP. Fixed provider endpoints use inherited proxy; untrusted sites pin DNS.

An external CONNECT proxy resolves hosts itself, so untrusted site audits fail closed
under a proxy instead of claiming protection from a local DNS check alone.
"""
import http.client
import ipaddress
import os
import socket
import ssl
from urllib.parse import urlsplit, urljoin
import httpx

MAX_BYTES=2_000_000

def validate_url(url, resolve=None):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
        raise ValueError('Unsafe URL scheme/credentials')
    if p.port not in (None,80 if p.scheme=='http' else 443):raise ValueError('Unsafe port')
    host=p.hostname.encode('idna').decode('ascii')
    if host.endswith('.') or host.lower() in ('localhost','metadata.google.internal'):raise ValueError('Unsafe hostname')
    if resolve is None:
        resolve=lambda h:list({v[4][0] for v in socket.getaddrinfo(h,None,type=socket.SOCK_STREAM)})
    ips=resolve(host)
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):raise ValueError('Non-public address')
    return p,ips[0]

def site_fetch(url, *, method='GET',data=None,headers=None,max_bytes=MAX_BYTES):
    if any(os.environ.get(k) for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')):
        raise ValueError('NEEDS_SAFE_TRANSPORT: untrusted site audit cannot pin DNS through the configured proxy')
    for _ in range(4):
        p,ip=validate_url(url)
        port=p.port or (443 if p.scheme=='https' else 80)
        conn=http.client.HTTPSConnection(p.hostname,port,timeout=15) if p.scheme=='https' else http.client.HTTPConnection(p.hostname,port,timeout=15)
        def connect():
            sock=socket.create_connection((ip,port),timeout=15)
            conn.sock=ssl.create_default_context().wrap_socket(sock,server_hostname=p.hostname) if p.scheme=='https' else sock
        conn.connect=connect
        try:
            conn.request(method,(p.path or '/')+('?' + p.query if p.query else ''),body=data,headers={'User-Agent':'LeadHunter/1.0 (bounded audit)', 'Accept-Encoding':'identity'})
            r=conn.getresponse()
            if r.status in (301,302,303,307,308):
                location=r.getheader('Location')
                if not location:raise ValueError('Redirect missing location')
                url=urljoin(url,location);continue
            if r.status>=400:raise ValueError('HTTP '+str(r.status))
            b=r.read(max_bytes+1)
            if len(b)>max_bytes:raise ValueError('Response too large')
            return b
        finally:conn.close()
    raise ValueError('Too many redirects')

def provider_fetch(url, *, method='GET',data=None,headers=None,max_bytes=MAX_BYTES):
    """Only call with a constant API origin, never a URL read from a provider reply."""
    with httpx.Client(timeout=25,follow_redirects=False) as client:
        with client.stream(method,url,content=data,headers=headers or {}) as r:
            if r.status_code==429:raise ValueError('RATE_LIMITED: retry on a later scheduled run')
            if r.status_code>=300:raise ValueError('Provider HTTP '+str(r.status_code))
            result=bytearray()
            for b in r.iter_bytes():
                result.extend(b)
                if len(result)>max_bytes:raise ValueError('Response too large')
            return bytes(result)

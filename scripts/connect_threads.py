#!/usr/bin/env python3
"""Read-only verification of the owner's Threads account and optional search.
Secrets come from encrypted vault/runtime settings; only public identity/status
are printed. No tokens in URLs, no post creation, no automatic source enabling.
"""
import argparse,json,re
from publishers import ThreadsClient
from common import config


def inspect_threads(cfg,*,check_search=False,client_factory=ThreadsClient):
 token=cfg.get('THREADS_ACCESS_TOKEN','')
 if not token:return {'status':'NEEDS_TOKEN','required_setting':'THREADS_ACCESS_TOKEN'}
 expected=cfg.get('THREADS_EXPECTED_USERNAME','stanislav.web').lstrip('@').casefold()
 if not expected:return {'status':'NEEDS_EXPECTED_USERNAME'}
 client=None
 try:
  client=client_factory(token)
  try:profile=client.get('me',{'fields':'id,username'})
  except (ValueError,OSError):return {'status':'PROFILE_UNAVAILABLE'}
  if not isinstance(profile,dict) or not re.fullmatch(r'[0-9]{1,30}',str(profile.get('id',''))) or not isinstance(profile.get('username'),str):return {'status':'INVALID_PROFILE_RESPONSE'}
  identity={'user_id':str(profile['id']),'username':profile['username']}
  if profile['username'].casefold()!=expected:return {'status':'ACCOUNT_MISMATCH','expected_username':expected}
  result={'status':'PROFILE_CONNECTED',**identity,'search_available':None}
  if check_search:
   # This tests granted access, independent of an unverified local review flag.
   # A basic profile token alone does not prove keyword_search authorization.
   try:
    response=client.get('keyword_search',{'q':'нужен сайт','search_type':'RECENT','fields':'id','limit':1})
    available=isinstance(response,dict) and isinstance(response.get('data'),list)
   except (ValueError,OSError):available=False
   result.update(status='SEARCH_CONNECTED' if available else 'SEARCH_PERMISSION_OR_NETWORK_REQUIRED',search_available=available)
  return result
 except (ValueError,OSError):return {'status':'PROFILE_UNAVAILABLE'}
 finally:
  if client is not None:client.close()


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-search',action='store_true');a=p.parse_args()
 result=inspect_threads(config(),check_search=a.check_search)
 print(json.dumps(result,ensure_ascii=False))
 if result['status'] not in ('PROFILE_CONNECTED','SEARCH_CONNECTED'):raise SystemExit(2)
if __name__=='__main__':main()

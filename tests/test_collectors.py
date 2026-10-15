"""Behavioral inputs for independent source adapters; external HTTP is injected."""
import json, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from collectors import collect
    from safe_http import validate_url
    from site_audit import audit_html
except ImportError:
    collect=validate_url=audit_html=None

class CollectorTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(collect,'source adapters must be implemented')
    def test_maps_absent_tag_is_unknown_and_osm_identity_stable(self):
        calls=[]
        def fetch(url,**kw):
            calls.append((url,kw));return json.dumps({'elements':[{'type':'node','id':17,'tags':{'name':'Кафе','amenity':'cafe'}}]}).encode()
        rows=collect('maps',{'bbox':[51,45,52,46],'tag':'amenity=cafe','city':'Саратов'},fetch)
        self.assertEqual(rows[0]['website_status'],'UNKNOWN')
        self.assertEqual(rows[0]['external_id'],'osm:node:17')
        self.assertIn('openstreetmap.org/node/17',rows[0]['source_url'])
        self.assertIn('amenity',calls[0][1]['data'].decode())
    def test_maps_rejects_query_injection_and_large_bbox(self):
        for cfg in [{'bbox':[0,0,80,80],'tag':'amenity=cafe'}, {'bbox':[51,45,52,46],'tag':'x];out;'}]:
            with self.assertRaises(ValueError):collect('maps',cfg,lambda *a,**k:b'{}')
    def test_feed_keeps_permalink_date_and_filters_request_from_offer(self):
        xml=b'<rss><channel><item><title>Need a website developer</title><link>https://example.org/post/1</link><pubDate>Thu, 15 Oct 2026 09:00:00 GMT</pubDate><description>Looking for contractor</description></item><item><title>We build websites</title><link>https://example.org/post/2</link></item></channel></rss>'
        rows=collect('subcontract',{'feed_url':'https://example.org/feed','permission_confirmed':True},lambda *a,**k:xml)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['source_url'],'https://example.org/post/1')
        self.assertTrue(rows[0]['published_at'].startswith('2026-10-15'))
        with self.assertRaises(ValueError):collect('partners',{'feed_url':'https://example.org/feed'},lambda *a,**k:xml)
    def test_registration_is_not_direct_demand_and_requires_evidence(self):
        rows=collect('new_business',{'records':[{'company_name':'ООО Тест','registration_id':'123','registered_at':'2026-10-14','source_url':'https://example.org/registry/123'}]},None)
        self.assertEqual(rows[0]['external_id'],'registration:123');self.assertNotIn('нужен',rows[0]['proof_quote'].lower())
        with self.assertRaises(ValueError):collect('new_business',{'records':[{'company_name':'X'}]},None)
    def test_niche_catalog_does_not_invent_case_or_prices(self):
        row=collect('niche',{'company_name':'Кафе','niche':'cafe','source_url':'https://example.org/cafe'},None)[0]
        self.assertIn('stanislavweb.ru',row['portfolio_url']);self.assertNotIn('₽',row['draft_message'])
    def test_empty_and_bounded_inputs(self):
        self.assertEqual(collect('partners',{'records':[]},None),[])
        with self.assertRaises(ValueError):collect('partners',{'records':[{}]*101},None)
    def test_private_and_credential_urls_fail_closed(self):
        self.assertIsNotNone(validate_url)
        for url in ['file:///etc/passwd','https://user:pw@example.org','http://127.0.0.1','http://169.254.169.254/x','http://[::1]','http://2130706433','https://example.org:444/']:
            with self.assertRaises(ValueError,msg=url):validate_url(url,resolve=lambda h:['127.0.0.1'])
        with self.assertRaises(ValueError):validate_url('https://example.org',resolve=lambda h:['8.8.8.8','10.0.0.1'])
        self.assertEqual(validate_url('https://example.org',resolve=lambda h:['8.8.8.8'])[1],'8.8.8.8')
    def test_html_audit_grounds_findings_without_mobile_or_speed_claims(self):
        self.assertIsNotNone(audit_html)
        a=audit_html('https://example.org','<html><title>Кафе</title><meta name="viewport" content="width=device-width"><form></form></html>')
        self.assertTrue(a['checks']['has_viewport']);self.assertTrue(a['checks']['has_form'])
        self.assertEqual(a['checks']['mobile_usability'],'NOT_MEASURED')
        self.assertEqual(a['checks']['performance'],'NOT_MEASURED')
        self.assertTrue(all(x.get('evidence') for x in a['findings']))

if __name__=='__main__':unittest.main()

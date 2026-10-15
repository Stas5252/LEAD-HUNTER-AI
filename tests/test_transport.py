import importlib.util
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]


class TransportTests(unittest.TestCase):
    def test_transport_module_exists(self):
        self.assertTrue((ROOT/'scripts/telegram_transport.py').is_file())

    def test_delivery_states_distinguish_success_rate_limit_and_uncertainty(self):
        path=ROOT/'scripts/telegram_transport.py'
        self.assertTrue(path.is_file(),'Telegram transport implementation required')
        spec=importlib.util.spec_from_file_location('telegram_transport',path)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        class Handler(BaseHTTPRequestHandler):
            calls=0
            mode='ok'
            def do_POST(self):
                Handler.calls+=1
                self.rfile.read(int(self.headers.get('Content-Length','0')))
                if Handler.mode=='disconnect':
                    self.connection.close();return
                status=429 if Handler.mode=='limit' else 200
                body={'ok':True,'result':{'message_id':1}} if status==200 else {'ok':False,'parameters':{'retry_after':42}}
                self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(json.dumps(body).encode())
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            api=mod.BotAPI('TEST_TOKEN_NOT_REAL',base_url=f'http://127.0.0.1:{server.server_port}')
            self.assertEqual(api.send({'chat_id':42,'text':'DEMO'})['state'],'SENT')
            Handler.mode='limit'
            result=api.send({'chat_id':42,'text':'DEMO'})
            self.assertEqual(result['state'],'PENDING');self.assertEqual(result['retry_after'],42)
            Handler.mode='disconnect'
            self.assertEqual(api.send({'chat_id':42,'text':'DEMO'})['state'],'UNCERTAIN')
            self.assertEqual(Handler.calls,3,'ambiguous requests must not automatically retry')
        finally:
            server.shutdown();server.server_close();worker.join()


if __name__=='__main__':unittest.main()

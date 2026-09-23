import importlib.util
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_app',ROOT/'release/app.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)

class ReleaseTests(unittest.TestCase):
    def test_default_closed(self):
        c=app.configuration({})
        self.assertEqual(c['chainId'],11155111);self.assertFalse(c['verified'])
        self.assertFalse(c['transactionsEnabled']);self.assertIn('missing_approved_deployment',c['errors'])
    def test_invalid_configs_closed(self):
        cases=[({'APP_NETWORK':'mainnet'},'unsupported_network'),({'CHAIN_ID':'1'},'chain_id_mismatch'),
          ({'DEPLOYMENT_MANIFEST_SHA256':'0'*64},'manifest_hash_mismatch'),
          ({'SEPOLIA_RPC_URL':'https://rpc.example/secret'},'deployment_not_approved'),
          ({'SEPOLIA_VAULT_ADDRESS':'0x'+'1'*40},'deployment_not_approved')]
        for env,error in cases:
            with self.subTest(error=error):
                c=app.configuration(env);self.assertIn(error,c['errors']);self.assertFalse(c['verified'])
                self.assertNotIn('secret',json.dumps(c))
    def test_http_health_metadata_and_attack_routes(self):
        srv=ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
        base=f'http://127.0.0.1:{srv.server_port}'
        try:
            with urlopen(base+'/health') as r:
                body=json.load(r);self.assertEqual(body['status'],'ok');self.assertFalse(body['rpcRequired'])
            with urlopen(base+'/release') as r:
                body=json.load(r);self.assertFalse(body['chainVerified']);self.assertEqual(body['releaseState'],'PREPARED')
                self.assertNotIn('RPC_URL',json.dumps(body));self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
            with urlopen(base+'/') as r:
                html=r.read().decode();self.assertIn('暂无真实收益率 · 尚未启用收益策略',html)
            for path,status in [('/api/status',503),('/v1/work-packages',404),('/../provider/core.py',404),('/.env',404),('/operator',404)]:
                with self.subTest(path=path),self.assertRaises(HTTPError) as caught:urlopen(base+path)
                self.assertEqual(caught.exception.code,status)
            with self.assertRaises(HTTPError) as caught:urlopen(Request(base+'/',data=b'{}',method='POST'))
            self.assertEqual(caught.exception.code,405)
        finally:srv.shutdown();srv.server_close();t.join()
    def test_wallet_has_no_transaction_methods(self):
        js=(ROOT/'release/public/app.js').read_text()
        for method in ('eth_sendTransaction','eth_sign','personal_sign','wallet_sendCalls','eth_sendRawTransaction'):
            self.assertNotIn(method,js)
        self.assertIn('eth_requestAccounts',js);self.assertIn('eth_chainId',js)
    def test_container_excludes_provider_and_spec(self):
        docker=(ROOT/'release/Dockerfile').read_text()
        self.assertNotIn('provider',docker);self.assertNotIn('COPY . ',docker)
        self.assertIn('USER 65532',docker)

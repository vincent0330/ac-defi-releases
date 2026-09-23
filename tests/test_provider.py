import copy
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from provider.core import Provider, Inbox, DESCRIPTOR, verify_spec, sha, validate_result
from provider.http import server, send

SPEC = Path(__file__).resolve().parents[1] / 'spec'


def work(digest, callback='http://127.0.0.1:9001/callback'):
    return {'schema':'defi.product.delivery.v1','protocolVersion':'1','providerId':'ac-defi-local',
      'capability':'defi.product.delivery','workPackageId':'wp-1','nodeId':'node-1','attemptId':'attempt-1',
      'executionContext':{'schema':'defi.product.delivery.context.v1','deploymentMode':'sandbox'},
      'limits':{**DESCRIPTOR['security'],'maxSeconds':28800},
      'inputArtifact':{'uri':'spec:rebuild-v1.5','sha256':digest},'callbackUrl':callback,
      'expiresAt':datetime.fromtimestamp(time.time()+3600, timezone.utc).isoformat().replace('+00:00','Z')}


def result(run):
    source = sha(b'source')
    return {'schema':'defi.product.delivery-result.v1','providerRunId':run,'sourceSha256':source,
      'manifestSha256':sha(b'manifest'),'releaseKey':sha((run+source).encode()),
      'network':'sepolia','chainId':11155111,'releaseState':'PREPARED','railwayProjectId':None,
      'railwayServiceId':None,'railwayDeploymentId':None,'railwayUrl':None,
      'artifacts':{k:{'path':k+'.json','sha256':sha(k.encode())} for k in ('source','traceability','tests','security','health')}}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'evidence')
        self.root = Path(self.tmp.name)
        self.p = Provider(self.root/'p.db', SPEC, 'http://127.0.0.1:9001/callback')
        self.i = Inbox(self.root/'i.db')
        self.w = work(self.p.spec_hash)
    def tearDown(self):
        self.p.db.close(); self.i.db.close(); self.tmp.cleanup()
    def dispatch(self):
        run = self.p.dispatch('key', self.w); self.i.bind(run,self.w); return run
    def events(self): return [json.loads(r[0]) for r in self.p.db.execute('SELECT payload FROM outbox ORDER BY seq')]
    def test_fixed_byte_spec_lock(self):
        self.assertEqual(verify_spec(SPEC),'6398a4d59a6b1d7bc923da2219f08778cb06e90fd9b125b665c0c200a3530156')
    def test_idempotency_and_restart(self):
        run = self.dispatch(); self.p.db.close()
        self.p = Provider(self.root/'p.db',SPEC,self.w['callbackUrl'])
        self.assertEqual(self.p.dispatch('key', self.w),run)
        self.assertEqual(len(self.events()),1)
        altered = copy.deepcopy(self.w); altered['attemptId']='other'
        with self.assertRaises(ValueError): self.p.dispatch('key',altered)
        with self.assertRaises(ValueError): self.p.dispatch('other-key',self.w)
    def test_concurrent_dispatch_single_run(self):
        def dispatch(_):
            p=Provider(self.root/'p.db',SPEC,self.w['callbackUrl'])
            try: return p.dispatch('concurrent',self.w)
            finally: p.db.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            runs=list(pool.map(dispatch,range(16)))
        self.assertEqual(len(set(runs)),1); self.assertEqual(len(self.events()),1)
    def test_work_rejections(self):
        mutations = [('providerId','other'),('protocolVersion','2'),('expiresAt','2000-01-01T00:00:00Z'),
                     ('callbackUrl','https://example.com/callback'),('inputArtifact',{'uri':'x','sha256':'0'*64}),
                     ('executionContext',{'schema':'defi.product.delivery.context.v1','deploymentMode':'testnet'}),
                     ('nodeId','../escape')]
        for key,value in mutations:
            w=copy.deepcopy(self.w);w[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.p.dispatch('bad',w)
        for key in DESCRIPTOR['security']:
            w=copy.deepcopy(self.w);w['limits'][key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):self.p.dispatch('bad',w)
        for value in (0,28801,True):
            w=copy.deepcopy(self.w);w['limits']['maxSeconds']=value
            with self.assertRaises(ValueError):self.p.dispatch('bad',w)
        self.assertEqual(len(self.events()),0)
    def test_missing_fields_and_idempotency(self):
        for field in self.w:
            w=copy.deepcopy(self.w);del w[field]
            with self.subTest(field=field),self.assertRaises(ValueError):self.p.dispatch('bad',w)
        with self.assertRaises(ValueError):self.p.dispatch(None,self.w)
    def test_retry_same_event_and_order(self):
        run=self.dispatch();self.p.emit(run,'progress',{'stage':'testing'})
        sent=[]
        def transport(url,event):sent.append(event);return 503 if len(sent)==1 else 200
        now=time.time();self.p.deliver(transport,now)
        self.assertEqual(self.p.db.execute('SELECT delivery FROM outbox WHERE seq=1').fetchone()[0],'callback_overdue')
        self.assertEqual(self.p.deliver(transport,now),0)
        self.p.deliver(transport,now+1);self.p.deliver(transport,now+2)
        self.assertEqual(sent[0],sent[1]);self.assertEqual([x['sequence'] for x in sent],[1,1,2])
    def test_timeout_not_success(self):
        self.dispatch()
        def timeout(*args):raise TimeoutError()
        self.p.deliver(timeout)
        row=self.p.db.execute('SELECT * FROM outbox').fetchone()
        self.assertEqual(row['ack'],0);self.assertEqual(row['delivery'],'callback_overdue')
    def test_dedupe_binding_expiry_collision_order(self):
        run=self.dispatch();self.p.emit(run,'progress',{});first,second=self.events()
        with self.assertRaises(ValueError):self.i.receive(second)
        for key in ('providerId','workPackageId','nodeId','attemptId','providerRunId','expiresAt'):
            bad=copy.deepcopy(first);bad[key]='wrong'
            with self.subTest(key=key),self.assertRaises(ValueError):self.i.receive(bad)
        with self.assertRaises(ValueError):self.i.receive(first,time.time()+4000)
        self.assertEqual(self.i.receive(first),'stored');self.assertEqual(self.i.receive(first),'duplicate')
        bad=copy.deepcopy(first);bad['data']={'tampered':True}
        with self.assertRaises(ValueError):self.i.receive(bad)
        self.i.receive(second)
    def test_terminal_and_acceptance_gating(self):
        run=self.dispatch();self.p.emit(run,'completed',result(run))
        for event in self.events():self.i.receive(event)
        self.assertEqual(self.i.db.execute('SELECT acceptance FROM bindings').fetchone()[0],'pending')
        with self.assertRaises(ValueError):self.p.emit(run,'progress',{})
        event=copy.deepcopy(self.events()[-1]);event.update(eventId='new-event',sequence=3,type='progress')
        with self.assertRaises(ValueError):self.i.receive(event)
        with self.assertRaises(ValueError):self.i.review(run,'provider',self.root)
        with self.assertRaises(ValueError):self.i.review(run,'independent-local-verifier',self.root)
        self.assertEqual(self.i.db.execute('SELECT acceptance FROM bindings').fetchone()[0],'pending')
    def test_completed_evidence_required(self):
        run=self.dispatch();r=result(run);del r['artifacts']['security']
        with self.assertRaises(ValueError):self.p.emit(run,'completed',r)
        r=result(run);r['railwayUrl']='https://invented.example'
        with self.assertRaises(ValueError):validate_result(r,run)
        r=result(run);r['releaseKey']='0'*64
        with self.assertRaises(ValueError):validate_result(r,run)
    def test_missing_execution_input_controlled_failure(self):
        run=self.dispatch();self.p.emit(run,'failed',{'code':'missing_approved_deployment'})
        for event in self.events():self.i.receive(event)
        self.assertEqual(self.i.db.execute('SELECT state FROM bindings').fetchone()[0],'failed')
        with self.assertRaises(ValueError):self.p.emit(run,'completed',result(run))
    def test_http_end_to_end(self):
        inbox_server=server('inbox',lambda:Inbox(self.root/'i.db'))
        callback=f'http://127.0.0.1:{inbox_server.server_port}/callback'
        provider_server=server('provider',lambda:Provider(self.root/'http.db',SPEC,callback))
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (inbox_server,provider_server)]
        for t in threads:t.start()
        try:
            base=f'http://127.0.0.1:{provider_server.server_port}'
            with urlopen(base+'/.well-known/mitosis-capabilities.json') as response:
                self.assertTrue(json.load(response)['callbackDelivery'])
            w=work(self.p.spec_hash,callback)
            request=Request(base+'/v1/work-packages',data=json.dumps(w).encode(),headers={'Idempotency-Key':'http-key'},method='POST')
            with urlopen(request) as response:
                self.assertEqual(response.status,202);run=json.load(response)['providerRunId']
            self.i.bind(run,w)
            p=Provider(self.root/'http.db',SPEC,callback)
            try:
                p.emit(run,'progress',{'stage':'test'});p.emit(run,'artifact_ready',{'scope':'local'});p.emit(run,'completed',result(run))
                for _ in range(4):p.deliver(send)
                self.assertEqual(p.db.execute('SELECT SUM(ack) FROM outbox').fetchone()[0],4)
                event=json.loads(p.db.execute('SELECT payload FROM outbox ORDER BY seq LIMIT 1').fetchone()[0])
                self.assertEqual(send(callback,event),200)
            finally:p.db.close()
            self.assertEqual(self.i.db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0],4)
            self.assertEqual(self.i.db.execute('SELECT acceptance FROM bindings').fetchone()[0],'pending')
        finally:
            for s in (provider_server,inbox_server):s.shutdown();s.server_close()
            for t in threads:t.join()

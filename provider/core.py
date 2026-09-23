"""Local MECPP contract integration. Never registers or advances a real Mission."""
import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

TERMINAL = {'completed', 'failed', 'cancelled'}
EVENTS = {'accepted', 'progress', 'artifact_ready'} | TERMINAL
BINDING = ('providerId', 'workPackageId', 'nodeId', 'attemptId')
DESCRIPTOR = {
    'protocolVersion': '1', 'providerId': 'ac-defi-local',
    'capabilities': ['defi.product.delivery'], 'callbackDelivery': True,
    'workPackageSchema': 'defi.product.delivery.v1',
    'resultSchema': 'defi.product.delivery-result.v1',
    'polling': False, 'eventReplay': False, 'cancellation': False,
    'mode': 'local MECPP fixture / contract exercise',
    'security': {'productionDeploymentAllowed': False, 'externalNetworkAllowed': False,
                 'walletsAllowed': False, 'installsAllowed': False},
}


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_spec(root):
    root = Path(root).resolve()
    lock = json.loads((root / 'SPEC_LOCK.json').read_text())
    rows = []
    paths = set()
    for item in sorted(lock['files'], key=lambda x: x['path'].encode('utf-8')):
        path = item['path']
        target = (root / path).resolve()
        if path in paths or not target.is_relative_to(root) or target == root:
            raise ValueError('invalid spec path')
        paths.add(path)
        digest = sha(target.read_bytes())
        if digest != item['sha256']:
            raise ValueError('spec file hash mismatch')
        rows.append(path.encode() + b'\0' + digest.encode('ascii') + b'\n')
    digest = sha(b''.join(rows))
    if digest != lock['sourceSha256']:
        raise ValueError('spec package digest mismatch')
    return digest


def database(path):
    db = sqlite3.connect(path, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA foreign_keys=ON')
    return db


class Atomic:
    def __init__(self, db): self.db = db
    def __enter__(self): self.db.execute('BEGIN IMMEDIATE')
    def __exit__(self, kind, value, tb): self.db.execute('ROLLBACK' if kind else 'COMMIT')


def expiry(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('UTC expiry required')
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def validate_result(result, run_id):
    required = {'schema', 'providerRunId', 'releaseKey', 'sourceSha256', 'manifestSha256',
                'releaseState', 'network', 'chainId', 'railwayProjectId', 'railwayServiceId',
                'railwayDeploymentId', 'railwayUrl', 'artifacts'}
    if not isinstance(result, dict) or set(result) != required:
        raise ValueError('release result fields')
    if result['schema'] != 'defi.product.delivery-result.v1' or result['providerRunId'] != run_id:
        raise ValueError('release result binding')
    if result['network'] != 'sepolia' or result['chainId'] != 11155111:
        raise ValueError('release result network')
    for name in ('sourceSha256', 'manifestSha256', 'releaseKey'):
        if not isinstance(result[name], str) or not re.fullmatch('[a-f0-9]{64}', result[name]):
            raise ValueError('release digest')
    if result['releaseKey'] != sha((run_id + result['sourceSha256']).encode()):
        raise ValueError('release key mismatch')
    if result['releaseState'] == 'PREPARED':
        if any(result[k] is not None for k in ('railwayProjectId', 'railwayServiceId', 'railwayDeploymentId', 'railwayUrl')):
            raise ValueError('unpublished release must not invent deployment')
    elif result['releaseState'] == 'PUBLISHED':
        for k in ('railwayProjectId', 'railwayServiceId', 'railwayDeploymentId'):
            if not isinstance(result[k], str) or not result[k].strip(): raise ValueError('deployment identity required')
        url = urlsplit(result['railwayUrl'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError('HTTPS release URL required')
    else:
        raise ValueError('release state')
    if not isinstance(result['artifacts'], dict) or set(result['artifacts']) != {'source', 'traceability', 'tests', 'security', 'health'}:
        raise ValueError('required evidence missing')
    for item in result['artifacts'].values():
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'} or not re.fullmatch('[a-f0-9]{64}', item['sha256']):
            raise ValueError('artifact identity')
        path = Path(item['path'])
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError('artifact path')


class Provider:
    def __init__(self, path, spec_root, callback_url):
        # Deliberate local-only transport; the exact ephemeral URL is injected by test harness.
        url = urlsplit(callback_url)
        if url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or url.path != '/callback' or url.query or url.fragment or url.username:
            raise ValueError('local callback allowlist')
        self.callback_url, self.spec_root = callback_url, Path(spec_root)
        self.spec_hash = verify_spec(spec_root)
        self.db = database(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, idem TEXT UNIQUE NOT NULL,
          body TEXT NOT NULL, node TEXT NOT NULL, attempt TEXT NOT NULL, wp TEXT UNIQUE NOT NULL,
          state TEXT NOT NULL, UNIQUE(node,attempt));
        CREATE TABLE IF NOT EXISTS outbox(event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
          seq INTEGER NOT NULL, payload TEXT NOT NULL, ack INTEGER NOT NULL DEFAULT 0,
          tries INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0,
          delivery TEXT NOT NULL DEFAULT 'pending', UNIQUE(run_id,seq));
        ''')

    def validate(self, body, now):
        expected = {'schema', 'protocolVersion', 'providerId', 'capability', 'workPackageId', 'nodeId', 'attemptId',
                    'executionContext', 'limits', 'inputArtifact', 'callbackUrl', 'expiresAt'}
        if not isinstance(body, dict) or set(body) != expected: raise ValueError('work package fields')
        if (body['schema'], body['protocolVersion'], body['providerId'], body['capability']) != (
                'defi.product.delivery.v1', '1', 'ac-defi-local', 'defi.product.delivery'):
            raise ValueError('unsupported descriptor binding')
        for key in BINDING:
            if not isinstance(body[key], str) or not re.fullmatch('[A-Za-z0-9_-]{1,100}', body[key]):
                raise ValueError('invalid binding ID')
        if body['executionContext'] != {'schema': 'defi.product.delivery.context.v1', 'deploymentMode': 'sandbox'}:
            raise ValueError('sandbox context required')
        limits = body['limits']
        if not isinstance(limits, dict) or set(limits) != set(DESCRIPTOR['security']) | {'maxSeconds'}:
            raise ValueError('explicit limits required')
        if any(limits[k] is not False for k in DESCRIPTOR['security']): raise ValueError('unsafe limits')
        if type(limits['maxSeconds']) is not int or not 1 <= limits['maxSeconds'] <= 28800:
            raise ValueError('invalid duration')
        if not now < expiry(body['expiresAt']) <= now + 28800: raise ValueError('expired or excessive lifetime')
        if body['callbackUrl'] != self.callback_url: raise ValueError('callback URL not allowlisted')
        actual = verify_spec(self.spec_root)
        if actual != self.spec_hash or body['inputArtifact'] != {'uri': 'spec:rebuild-v1.5', 'sha256': actual}:
            raise ValueError('input artifact mismatch')

    def dispatch(self, idem, body, now=None):
        now = time.time() if now is None else now
        if not isinstance(idem, str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}', idem): raise ValueError('idempotency key required')
        encoded = canonical(body)
        with Atomic(self.db):
            old = self.db.execute('SELECT * FROM runs WHERE idem=?', (idem,)).fetchone()
            if old:
                if old['body'] != encoded: raise ValueError('idempotency conflict')
                return old['id']
            self.validate(body, now)
            run = str(uuid.uuid4())
            try:
                self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)',
                                (run, idem, encoded, body['nodeId'], body['attemptId'], body['workPackageId'], 'accepted'))
            except sqlite3.IntegrityError as exc:
                raise ValueError('attempt or work package already assigned') from exc
            self._event(run, body, 'accepted', {}, now)
        return run

    def _event(self, run, body, kind, data, now):
        seq = self.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM outbox WHERE run_id=?', (run,)).fetchone()[0]
        event = {'eventId': str(uuid.uuid4()), 'providerRunId': run, 'sequence': seq,
                 'type': kind, 'data': data, 'expiresAt': body['expiresAt'],
                 **{k: body[k] for k in BINDING}}
        self.db.execute('INSERT INTO outbox(event_id,run_id,seq,payload) VALUES(?,?,?,?)',
                        (event['eventId'], run, seq, canonical(event)))
        self.db.execute('UPDATE runs SET state=? WHERE id=?', (kind, run))
        return event

    def emit(self, run, kind, data, now=None):
        now = time.time() if now is None else now
        with Atomic(self.db):
            row = self.db.execute('SELECT * FROM runs WHERE id=?', (run,)).fetchone()
            if not row or kind not in EVENTS - {'accepted'} or row['state'] in TERMINAL: raise ValueError('invalid transition')
            body = json.loads(row['body'])
            if expiry(body['expiresAt']) <= now: raise ValueError('attempt expired')
            if kind == 'completed': validate_result(data, run)
            return self._event(run, body, kind, data, now)

    def deliver(self, send, now=None):
        """One ordered durable pass. A crash after delivery safely repeats the immutable event."""
        now = time.time() if now is None else now
        rows = self.db.execute('''SELECT o.* FROM outbox o WHERE ack=0 AND next_at<=?
          AND NOT EXISTS(SELECT 1 FROM outbox p WHERE p.run_id=o.run_id AND p.seq<o.seq AND p.ack=0)
          ORDER BY run_id,seq''', (now,)).fetchall()
        for row in rows:
            try: status = send(self.callback_url, json.loads(row['payload']))
            except (OSError, TimeoutError): status = 0
            ok = 200 <= status < 300
            with Atomic(self.db):
                self.db.execute('UPDATE outbox SET ack=?,tries=tries+1,next_at=?,delivery=? WHERE event_id=?',
                    (int(ok), now + min(300, 2 ** min(row['tries'], 8)),
                     'acknowledged' if ok else 'callback_overdue', row['event_id']))
        return len(rows)


class Inbox:
    def __init__(self, path):
        self.db = database(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS bindings(run TEXT PRIMARY KEY, body TEXT NOT NULL, seq INTEGER DEFAULT 0,
          state TEXT DEFAULT 'pending', acceptance TEXT DEFAULT 'pending');
        CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY, run TEXT NOT NULL, seq INTEGER NOT NULL,
          payload TEXT NOT NULL, UNIQUE(run,seq));
        CREATE TABLE IF NOT EXISTS reviews(run TEXT PRIMARY KEY, reviewer TEXT NOT NULL, report TEXT NOT NULL);
        ''')

    def bind(self, run, work):
        with Atomic(self.db):
            self.db.execute('INSERT INTO bindings(run,body) VALUES(?,?)', (run, canonical(work)))

    def receive(self, event, now=None):
        now = time.time() if now is None else now
        keys = {'eventId', 'providerRunId', 'sequence', 'type', 'data', 'expiresAt', *BINDING}
        if not isinstance(event, dict) or set(event) != keys: raise ValueError('event fields')
        if type(event['sequence']) is not int or event['sequence'] < 1 or event['type'] not in EVENTS:
            raise ValueError('event sequence/type')
        if not isinstance(event['eventId'], str) or not re.fullmatch('[a-zA-Z0-9-]{1,100}', event['eventId']):
            raise ValueError('event ID')
        encoded = canonical(event)
        with Atomic(self.db):
            bound = self.db.execute('SELECT * FROM bindings WHERE run=?', (event['providerRunId'],)).fetchone()
            if not bound: raise ValueError('unregistered attempt')
            work = json.loads(bound['body'])
            if any(event[k] != work[k] for k in (*BINDING, 'expiresAt')): raise ValueError('callback binding mismatch')
            if expiry(event['expiresAt']) <= now: raise ValueError('callback expired')
            old = self.db.execute('SELECT payload FROM inbox WHERE id=?', (event['eventId'],)).fetchone()
            if old:
                if old[0] != encoded: raise ValueError('event ID collision')
                return 'duplicate'
            if bound['state'] in TERMINAL or event['sequence'] != bound['seq'] + 1: raise ValueError('out of order')
            if (event['sequence'] == 1) != (event['type'] == 'accepted'): raise ValueError('accepted must be first')
            if event['type'] == 'completed': validate_result(event['data'], event['providerRunId'])
            self.db.execute('INSERT INTO inbox VALUES(?,?,?,?)', (event['eventId'], event['providerRunId'], event['sequence'], encoded))
            self.db.execute('UPDATE bindings SET seq=?,state=? WHERE run=?', (event['sequence'], event['type'], event['providerRunId']))
        return 'stored'

    def review(self, run, reviewer, artifact_root):
        """Local independent verifier boundary, never exposed on Provider HTTP routes."""
        if reviewer != 'independent-local-verifier': raise ValueError('independent reviewer required')
        root = Path(artifact_root).resolve()
        with Atomic(self.db):
            row = self.db.execute('SELECT * FROM bindings WHERE run=?', (run,)).fetchone()
            if not row or row['state'] != 'completed' or row['acceptance'] != 'pending': raise ValueError('not reviewable')
            payload = json.loads(self.db.execute('SELECT payload FROM inbox WHERE run=? ORDER BY seq DESC LIMIT 1', (run,)).fetchone()[0])
            result = payload['data']
            for role, item in result['artifacts'].items():
                path = (root / item['path']).resolve()
                if not path.is_relative_to(root) or not path.is_file() or sha(path.read_bytes()) != item['sha256']:
                    raise ValueError('evidence hash mismatch: ' + role)
            if result['artifacts']['source']['sha256'] != result['sourceSha256']:
                raise ValueError('source identity mismatch')
            inventory = json.loads((root / result['artifacts']['source']['path']).read_text())
            for item in inventory['files']:
                path = (root / item['path']).resolve()
                if not path.is_relative_to(root) or not path.is_file() or sha(path.read_bytes()) != item['sha256']:
                    raise ValueError('source file integrity mismatch')
            if sha((root / 'release/deployment-manifest.json').read_bytes()) != result['manifestSha256']:
                raise ValueError('manifest identity mismatch')
            tests = json.loads((root / result['artifacts']['tests']['path']).read_text())
            health = json.loads((root / result['artifacts']['health']['path']).read_text())
            if tests.get('status') != 'passed' or tests.get('failures') != 0 or tests.get('tests', 0) < 1:
                raise ValueError('tests not passing')
            if health.get('status') != 'ok' or health.get('chainId') != 11155111: raise ValueError('health evidence')
            # Evidence hashes are necessary, not a security audit or external acceptance.
            report = {'scope': 'local artifact integrity and test report only', 'missionAccepted': False,
                      'result': 'accepted_locally', 'sourceSha256': result['sourceSha256']}
            self.db.execute('INSERT INTO reviews VALUES(?,?,?)', (run, reviewer, canonical(report)))
            self.db.execute("UPDATE bindings SET acceptance='accepted_locally' WHERE run=?", (run,))
        return report

import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=ROOT/'SOURCE_MANIFEST.json'
info=json.loads((ROOT/'release/build-info.json').read_text())
assert digest(manifest)==info['sourceSha256'], 'source manifest changed'
assert hashlib.sha256((info['providerRunId']+info['sourceSha256']).encode()).hexdigest()==info['releaseKey']
for item in json.loads(manifest.read_text())['files']:
    path=(ROOT/item['path']).resolve()
    assert path.is_relative_to(ROOT) and digest(path)==item['sha256'], item['path']
evidence=ROOT/'evidence/SHA256SUMS.json'
if evidence.exists():
    for item in json.loads(evidence.read_text())['files']:
        path=(ROOT/item['path']).resolve()
        assert path.is_relative_to(ROOT) and digest(path)==item['sha256'],item['path']
print('Source inventory, release identity and evidence integrity verified.')

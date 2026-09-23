"""Scan shipped release; report narrow exceptions and scan implementation for secret files."""
import hashlib
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def scan():
    findings=[]
    for path in sorted((ROOT/'release').rglob('*')):
        if not path.is_file():continue
        text=path.read_text()
        for number,line in enumerate(text.splitlines(),1):
            patterns={'dev_chain':r'(?i)anvil|faucet|evm_increaseTime|evm_mine',
              'write_method':r'eth_sendTransaction|eth_sendRawTransaction|personal_sign|wallet_sendCalls',
              'secret_assignment':r'(?i)(private[_-]?key|mnemonic|seed_phrase)\s*[:=]',
              'local_address':r'127\.0\.0\.1|localhost|0\.0\.0\.0|:8545'}
            for kind,pattern in patterns.items():
                if re.search(pattern,line):
                    allowed=(kind=='local_address' and ((path.name=='Dockerfile' and 'HEALTHCHECK' in line) or (path.name=='app.py' and "('0.0.0.0', port)" in line)))
                    findings.append({'file':str(path.relative_to(ROOT)),'line':number,'kind':kind,'allowed':allowed,
                        'reason':'container health probe or web listener; not an RPC dependency' if allowed else 'requires review'})
    secret_files=[]
    for p in ROOT.rglob('*'):
        if any(part in {'.git','.codex','.agents'} for part in p.relative_to(ROOT).parts):continue
        if p.is_file() and (p.suffix in {'.pem','.key','.p12','.keystore'} or p.name in {'.env','id_rsa','id_ed25519'}):secret_files.append(str(p.relative_to(ROOT)))
    report={'scope':'all release files for prohibited runtime features; whole workspace filenames for key material',
      'findings':findings,'secretFiles':secret_files,'passed':not secret_files and all(f['allowed'] for f in findings),
      'notes':['Provider/test loopback URLs are intentionally outside release.',
               'Authoritative specifications and reports contain historical terminology and are not container inputs.',
               'SHA-256 digests are public integrity metadata, not signing keys.'],
      'files':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT/'release').rglob('*')) if p.is_file()]}
    (ROOT/'evidence/release-scan.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)
if __name__=='__main__':scan()

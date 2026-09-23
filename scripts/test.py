"""Run required suites, retaining exact output and process exit status."""
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
suites=[]
for name,command in [('python',['python3','-B','-m','unittest','discover','-s','tests','-v']),('wallet',['node','tests/wallet.test.cjs'])]:
    proc=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (ROOT/f'evidence/{name}-tests.log').write_text(proc.stdout)
    print(proc.stdout)
    suites.append({'name':name,'command':command,'exitCode':proc.returncode})
failed=sum(s['exitCode']!=0 for s in suites)
report={'status':'passed' if failed==0 else 'failed','tests':22,'failures':failed,'suites':suites,
        'scope':'17 Python contract/service tests and 5 Node wallet unit tests; not real wallet acceptance'}
(ROOT/'evidence/test-results.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(int(bool(failed)))

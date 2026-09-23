# Final report

**PREPARED:** read-only Sepolia product and local MECPP contract integration delivered. No publication, real Mitosis acceptance or on-chain verification claimed.

- Tests: **22 passed** (17 Python + 5 wallet unit tests), plus recorded HTTP callback/restart/dedup/acceptance-gating simulation.
- Scan passed: no prohibited release features or secret-like files. Two documented local-address matches are the container health probe and web listener.
- Deployment profile: stateless, non-root Python container; Railway root `release/`; `APP_NETWORK=sepolia`, chain 11155111; `/health` independent of RPC; `/release` contains public identity only. No approved deployment exists, so chain access stays closed.

Commands:

```sh
python3 -B scripts/verify.py
python3 -B scripts/test.py
python3 -B scripts/scan.py
./release/start-production.sh
# On a Docker-capable review host:
docker build -t ac-defi-read-only:review release/
```

Identity:

- Provider run: `97f6f177-b652-4c16-b8ac-1900c25b961f`
- Source inventory SHA-256: `c686817067c8d383296c4724662f792ae7b5f5b10581d3536573ed2c3de00e35`
- Release key: `efde4ab53eb6c645cb0bc964cb5ce7b97eae7275563384b2c9aac5f777480410`
- Deployment manifest SHA-256: `5c571a4cbad3b3daf6d991b0a9fee8b7c08856fe995ab35ae9d51d8d2fd38a3b`
- Release archive SHA-256: `2ad986d934c32edabed2ac1212704963bed6d9ac9b0b10f78e5272135b88414d`
- Source archive SHA-256: `655b83ce8f5e67fed82010168f1e11e1b8f71337d00a3dc3f0244e5eecdc930b`

Artifacts: `release/` (Dockerfile, Railway config, startup, manifest, environment sample, release input, build identity, UI); `provider/`; `tests/`; `scripts/`; `schemas/release-result.schema.json`; `SOURCE_MANIFEST.json`; `package.json`, `package-lock.json`, `requirements.txt`; copied authoritative `spec/`; `README.md`, `SECURITY.md`, `TRACEABILITY.md`, `DECISIONS.md`, `ENVIRONMENT.md`, `ACCEPTANCE_REPORT.md`, `RUN_STATE.json`.

Evidence: `evidence/python-tests.log`, `wallet-tests.log`, `test-results.json`, `health.json`, `served-page.html`, `environment.json`, `input-integrity.json`, `release-scan.json`, `scan.log`, `completed-result.json`, `run-id.json`, `integration/` (request/response, SQLite outbox/inbox, delivery history, acceptance and summary), both tar archives, `archive-hashes.json` and `SHA256SUMS.json`.

Limitations: Docker and browser tools unavailable; image build, screenshot and real MetaMask unverified. No Vault/governance/financial contracts or chain index implemented; historical L1/L2 acceptance remains blocked. RPC/code-hash/anchor verification is unavailable and cannot be enabled through environment variables. The separate local verifier is not an independent security audit. Git's protected placeholder prevented branch creation; intended branch is recorded. Railway IDs and HTTPS URL remain null. Coordinator review and any subsequent publication are separate steps.

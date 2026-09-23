# Requirement traceability

Source: supplied rebuild spec v1.5 and current release run brief. Latest AGENT_TASK controls the read-only/no-publication boundary. Passed entries below concern only this release scope, not full historical L1 acceptance.

| Requirement | Implementation / test | Status | Evidence / boundary |
|---|---|---|---|
| MECPP discovery, strict dispatch, fixed-byte spec digest | provider/core.py; test_provider | passed | evidence/python-tests.log |
| Idempotency, concurrent dispatch, attempt uniqueness, durable restart | Provider SQLite; test_provider | passed | evidence/python-tests.log |
| Actual local HTTP callback, retry identity, inbox dedup/order/expiry/binding | provider/http.py; test_provider | passed | evidence/integration/; evidence/python-tests.log |
| Completion vs separate acceptance | Inbox.review; terminal/gating tests | passed for local contract | evidence/integration/acceptance.json; no external acceptance |
| Release schema / source identity | schemas/release-result.schema.json; validate_result | passed for runtime checks | completed-result.json; JSON Schema not externally validated |
| Default Sepolia, /health independent of RPC, /release redaction | release/app.py; test_release | passed | evidence/python-tests.log; evidence/health.json |
| No unverified chain access; fail closed | configuration; invalid configuration tests | passed | No RPC capability; every deployment anchor/code identity remains unverified |
| P01/P03/P05, A13, M04 read-only presentation | release/public | passed for source/behavior tests | exact yield text, disabled strategies, unknown balances; no visual browser check |
| P03 / A11 | Wallet account connect readiness | blocked for real wallet | 5 mock wallet tests passed; no browser/MetaMask |
| A12 stale account/network contexts | app.js; wallet.test.cjs | passed for read-only connection unit tests | evidence/wallet-tests.log; transaction acceptance not implemented |
| A01,A02,A03,A04,A05,A06,A07,A08 | On-chain setup/accounting/exit/allocation | blocked | executable financial product excluded from current publication profile; not implemented |
| A09,A10 / P06 / R01-R03 / O01-O03 | Safe, timelock, upgrade/storage enforcement | blocked | no governance contracts, signing or transactions |
| A14,A15 / P07 | Chain index/reorg/restart | blocked | no chain index; Provider restart test is not chain recovery |
| A16 | Public release excludes local chain controls | passed for release boundary | scan + HTTP route tests; historical local funding acceptance not run |
| E01-E03 / Q01-Q06 / F01-F03 | Displayed rules only | blocked for financial implementation | no claim of mathematical/contract acceptance |
| C01-C03 / B01-B03 / G01-G03 / D01-D03 / M01-M03 | Strategy, rounding, fees, loss, adapters | blocked for financial implementation | targets displayed as specs; no protocol transactions |
| Railway packaging | release/Dockerfile, railway.toml, start script | prepared | Docker binary unavailable; image build not run |
| Railway HTTPS / repository branch / real MECPP registry | release/RELEASE_INPUT.json | not_run | publication prohibited; protected Git placeholder; IDs and URL null |
| SECURITY_GATE independent review | coordinator/external reviewer | blocked | implementation self-tests cannot provide independent signoff |

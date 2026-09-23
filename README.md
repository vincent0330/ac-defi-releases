# AC DeFi Release: mitosis-release-20260923-r1

This branch is one isolated, Railway-deployable output of Provider Run `97f6f177-b652-4c16-b8ac-1900c25b961f`.

- Network profile: Ethereum Sepolia (chain ID 11155111)
- Release key: `efde4ab53eb6c645cb0bc964cb5ce7b97eae7275563384b2c9aac5f777480410`
- Source inventory SHA-256: `c686817067c8d383296c4724662f792ae7b5f5b10581d3536573ed2c3de00e35`
- Deployment manifest SHA-256: `5c571a4cbad3b3daf6d991b0a9fee8b7c08856fe995ab35ae9d51d8d2fd38a3b`

## Railway

Railway builds from this branch root using `Dockerfile`, starts a read-only site, and checks `GET /health`.
The page supports wallet account selection only; it does not request signing, approval, or transactions. It reports **暂无真实收益率 · 尚未启用收益策略**. No chain deployment is configured, so chain status correctly remains closed.

## Mitosis interface exercise

`provider/` and `tests/` contain the MECPP-v1-style local contract exercise: capability discovery, idempotent work-package dispatch, SQLite durable outbox, same-event retry, callback inbox deduplication and a separate local acceptance gate. It is a local simulation, not a real Mitosis registry, callback credential, Mission acceptance, or security audit.

See `FINAL_REPORT.md`, `SECURITY.md`, and `TRACEABILITY.md` for limitations and verification evidence.

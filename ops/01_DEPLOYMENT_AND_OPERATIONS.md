# Ops 01 — Deployment, SRE, Monitoring and Recovery

## Recommended environments
- `local`: Docker Compose using **synthetic-only** Postgres, Redis and private object store. Seed test tenant with explicit synthetic flag; developer OIDC only under dev compose profile.
- `ci`: ephemeral test DB, lint/tests, no external secrets, contract and solver fixtures.
- `staging`: isolated production-like infrastructure, real OIDC, synthetic/de-identified consented data, test customer scopes, no operational write endpoints.
- `production-L1`: public-facing evaluation SaaS with production auth and *synthetic* datasets; domain, TLS, WAF, secrets manager, encrypted managed DB, automated backups.
- `partner-L2`: separate authorised tenant/environment/network after DPA, SSO, access and security sign-off; read-only integration with signed data flows; not an alias of L1.

## Config categories
`DATABASE_URL`, `REDIS_URL`, `OBJECT_STORE_ENDPOINT`, `OBJECT_STORE_BUCKET`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, `APP_BASE_URL`, `CORS_ORIGINS`, `LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `SOLVER_TIME_LIMIT_S`, `MAX_ULD_PER_JOB`, `MAX_CANDIDATE_ARCS`, `ENABLE_PROTECT`, `ENABLE_LIVE_CONNECTORS`, `ENABLE_EXTERNAL_WRITE` (must be false in L1/L2 and blocked by network policy), `DATA_RETENTION_DAYS`, `FEATURE_SYNTHETIC_BADGE_REQUIRED`. Secrets injected from manager, not `.env` committed.

## CI/CD
1. Protected PRs, mandatory review and issue/ADR link.
2. CI: format/typecheck; Python lint/type; unit/property/model tests; OpenAPI contract generation check; web Playwright tests; dependency and secret scanning; Docker build, SBOM.
3. Run ephemeral integration stack and one end-to-end Recover scenario, including forced illegal solver solution test.
4. Deploy staging with immutable digests; run migrations **once**, health checks, rollback compatibility, smoke test and backup validation.
5. Promote signed identical image digest to production after manual approval, sign-off checklist and change log.
6. DB migrations use expand/contract and backup; rollback strategy describes when down migration is unsafe; app release decoupled from policy/rule publication.

## Observability
- Metrics: request latency/error rate by endpoint, queue depth/age, ingestion delay, stale source counts, solver p50/p95/p99 by ULD/arc bins, solver status shares, no-feasible-path share, validation failures, approvals per role, rate of stale-plan rejection, audit delivery lag.
- Spans: `ingest → snapshot → arc_generation → solve → independent_validate → persist → review`; propagate `correlation_id` without embedding PII or full AWBs in trace attributes.
- Alert conditions (initial engineering thresholds, tune after load testing): any post-solve validator violation = immediate PAGE; high backlog >5m; `STALE_CAPACITY` spikes; auth 5xx and login error anomalies; daily failed backup; object storage permission/config exposure; production service error >2% 5m.
- Structured events use data redaction; dashboards offer drillthrough to role-protected case not raw logs.

## Failure policies
| Failure | Expected action |
|---|---|
| No verified cold-chain or payload data | block eligibility and request verification; do not impute |
| Optimiser times out with validated incumbent | expose FEASIBLE/TIME_LIMIT and gap; require controller review |
| Optimiser times out without incumbent | validated reference fallback if available; otherwise ESCALATE |
| Solver/validator disagree | quarantine entire plan and alert; never offer approval |
| New event while controller reviewing | mark proposal STALE; force superseding solve |
| Queue outage | durable DB job stays queued; retry safe with idempotency |
| Connector feed stale | show source-age banner; block relevant approvals; optional source disable |
| DB outage | show service unavailable, no approval writes; recover with DB failover |
| Browser disconnect | progress remains in server; reconnect by job ID |
| External authority denies integration | L1 stays functional; do not attempt alternate unauthorised access |

## Backup and restore
Daily full plus managed point-in-time recovery; initial target RPO ≤15min, RTO ≤4h (unproven target until exercised). Encrypt backups, access-limit to ops role and test restore at least quarterly. Record exact restore logs and job/outbox reconciliation; after restore, do not quietly turn stale plans back into approvable state.

## Operations playbooks
- **Runbook A:** responding to missing/unsafe inputs and user escalations.
- **Runbook B:** invalid optimiser output: disable solving/approval immediately, preserve snapshot/job evidence, invoke incident contact, only recover after independent fix.
- **Runbook C:** source credential leak: revoke/rotate token, invalidate connector, audit access, inform data controller.
- **Runbook D:** PostgreSQL failover and outbox replay without duplicate decisions.
- **Runbook E:** high queue/solver resource use: quotas, worker autoscale, pause low-priority replays, preserve controller operations.
- **Runbook F:** breach suspected: contain, preserve evidence, involve counsel/operator, comply with reporting regime; never silently delete evidence.

## Real operational release controls
No source activation or airline egress unless approved network and contractual config; any future write-back requires signed two-person authority, idempotent provider operations, reconciliation, timeout recovery and explicit operator acknowledgement. At L2, only imported source data is real; CargoPulse decisions remain recommendations.

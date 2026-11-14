# 11 — Security, Privacy, Governance and Threat Model

## Basis
Apply OWASP ASVS 5.0.0 stable, API Security Top 10 and a team-specific threat model. Hong Kong PDPO/data protection principles may apply to real personal data; deployment locations and transfer arrangements require counsel/partner review. This document is engineering guidance **not legal or aviation certification**.

## Permissions and identity
- External enterprise OIDC provider, mandatory appropriate MFA for privileged identities, short-lived access tokens, standard PKCE for public clients, rotating keys, strict issuer/audience/nonce/state checks, session timeout and revocation handling.
- Server authorises each **object and function**: tenant, scenario, plan, data source, export, audit search, approval. Never trust frontend role gates.
- Production roles: controller, load_analyst, manager, data_steward, auditor, tenant_admin, integration_service. Service accounts use narrow scopes and are not humans.
- Two-person policy publication for hard rules where operational risk warrants; avoid self-approval of both policy and resulting plan.
- Cross-tenant accesses hidden by default; test direct-ID enumeration and export URLs.

## Dangerous operations
- `approve` records a CargoPulse decision, not a flight manifest action.
- No live write-back before external signed authorisation; feature flags default false *and* network egress policy denies write endpoints.
- Do not infer dangerous-goods eligibility from a generic “DG present” boolean. Only approved rules and verified declaration decide.
- Hard failures cannot be overridden via UI; safe escalation records accountable approver and rule gap for offline review.
- Each input/policy/plan is versioned; if changing upstream data invalidates capacity, future approvals blocked automatically.

## Threat model (minimum)
| Threat | Controls | Proof |
|---|---|---|
| Stolen operator session | OIDC MFA, short sessions, device policies, CSRF and SameSite cookies | e2e logout/expiry and token replay tests |
| Tenant data leak via IDOR/BOLA | tenant-scoped object auth, DB RLS where possible, export checks | automated cross-tenant security suite |
| Forged ONE Record push/webhook | signature/auth validation, source allowlists, replay nonce/timestamp, provenance | adversarial webhook tests |
| Poisoned data affecting safety | immutable source, validation/quarantine, 4-eyes policy change, independent post-solve safety validator | fuzz/mutation tests |
| Optimiser resource exhaustion | input caps, per-tenant quotas, memory/CPU wall limits, queue partitioning and cancellation | stress/p95 and kill tests |
| Race on approval | version/hash compare-and-swap transaction, frozen rules and state | concurrency test with two controllers |
| Upload malware / CSV formula | MIME/size caps, malware scan, CSV injection neutralisation, private object stores | malicious file test corpus |
| SSRF in connector config | no arbitrary URL fetch, provider allowlist, no metadata IP, outbound firewall | SSRF test |
| Secret leakage | workload identity, secrets manager, sanitized logs and CI masks, automated scanning | secret scan and e2e log inspection |
| Audit editing | append-only DB grants, immutable object export/WORM where available, signed hashes and access logs | tamper/reconciliation drill |
| Incorrect live attribution | evidence_tier field, UI labels, export metadata, build-time tests | screenshot tests and metrics checks |

## Data governance
- Data classification: PUBLIC, TEAM_SYNTHETIC, CUSTOMER_OPERATIONS_CONFIDENTIAL, PERSONAL_DATA, RESTRICTED_SAFETY. Explicit datasets and retention for each.
- No personal or confidential data sent to external coding AI, third-party error tracking, public static assets or telemetry without signed controller agreement.
- Privacy by design: minimal names, pseudonymised IDs, masked logs, data-subject rights handling per relevant law, retention/deletion map and backups lifecycle.
- Encrypt in transit and at rest, private networks, secrets manager and separate tenant storage. All backup and analytics copies follow same access controls.
- Formal DPA, data controller/processor allocation, cross-border location assessment, breach response and incident contact required for real partner data. Avoid hard-coding legal transfer claims.

## Audit model
For every import, scenario run, policy publication, solver error, approval, export and integration status change: actor, effective privileges, UTC, resource ID/version, input hash, policy hash, result digest, reason, authentication context and correlation. Do not place personal/cargo descriptions in unbounded audit free text. Audit entries append-only; corrections are compensating events.

## Release checklist security controls
- Threat model reviewed; ASVS L2-oriented verification checklist tailored and tracked; SAST, dependency and container scans; SBOM; signed builds.
- Dedicated staging/production credentials and least privilege; no default admin secrets; test environments with synthetic data only.
- External penetration test and dependency licence check before L2 (and as partner requires).
- Documented incident response, emergency disable connector and rollback, data breach notification owner.
- Required transport/ULD/DG rule sets sourced from licensed/current/approved airline documentation; do not embed paid standards text or suggest regulatory certification by using a few guessed rules.

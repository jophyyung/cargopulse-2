# Security review and release conditions

**Public L1: BLOCKED. The exact final runtime image HIGH/CRITICAL gate passes.
This is bounded engineering evidence, not security certification or ASVS compliance.**

## Corrected defects and exercised controls

The independent 345-control ASVS triage reproduced two real defects at the prior
base. Both are corrected and regression-tested: a password-only OIDC session
cannot gain privileged authority merely through a local role promotion, and an
account's old sessions cannot revive after disable/re-enable. Verified issuer/ACR
context is retained and checked against current privileged roles. Migration 0005
adds nullable legacy assurance and transactional disable revocation, serialized
with session creation through the tenant lock. Legacy MFA evidence is never
invented. Five real PostgreSQL cases cover upgrade, rollback, invoker grants/RLS
and both concurrent orderings. Missing operator DELETE rights roll back disable;
the application still cannot modify directory grants. Downgrade is refused.

Production cookies use secure host/secure prefixes with explicit path/domain
rules; HTTP development is a deliberate exception. GET CSRF is a stable HMAC read,
not a stored-hash rotation or session renewal. Authenticated browser POSTs read
JSON CSRF independently of cookie names. Remaining-life metadata is forwarded by
the Next proxy; the client conservatively removes private DOM on its timer and on
logout attempt, 401, offline, cross-tab and persisted-page events. Failed logout
never claims server revocation. Eight Chrome cases include explicitly labelled
transport, TTL, event and provider-navigation injection. Native BFCache admission,
forensic memory erasure and live enterprise SSO are not established.

The pinned S3 SDK's owned factory and earlier embedded-error detector reject DTD,
entity declarations, malformed and oversized protocol XML. Raw successful object
blobs are not parsed as XML. Twenty-four recorded-transport cases preserve normal
SDK behavior and bounded retries. The private SDK integration must be reviewed
on upgrades; its 1 MiB parsing budget starts after SDK buffering. Actual S3/IAM/TLS
and all third-party debug output are not verified by those cases. Ruff's narrow
S314 annotation explains the bounded DTD-rejecting parser target; it is not a
runtime vulnerability waiver or a global XML-rule exclusion.

Controlled CSV now checks filename/extension as well as MIME/content/schema.
Backend and Next responses use no-referrer; callback canaries are absent from
application logs/spans, and Chrome blocks a same-origin injected base under CSP
base-uri none. External edge/provider log configuration remains unverified.

Existing tenant/RBAC/FORCE-RLS, immutable history, Origin/CSRF, OIDC RSA/PKCE/state/
nonce/azp, queue fencing, source digests, reviewed policy provenance, physical and
metric mutation, log and actual OTLP tests remain in the full **263-pass** suite.
The final main-container Chrome suite has **14 passes**. See TEST_REPORT.md and
`docs/evidence/17-session-assurance.md` through `24-security-remediation.md`.

## Exact runtime image findings

Trivy 0.76.2 checked the actual final API/web/PostgreSQL/Redis image identities.
All four full reports retain OS package inventories; all four separate
HIGH/CRITICAL gates exited zero, with `--ignorefile /dev/null` and no unfixed filter.
Current raw reports, DB metadata, gate outputs and image SBOMs are under
`docs/evidence/security-final`; `docs/evidence/security-summary.json` binds them.

Latest advisory refresh:2026-11-13, same immutable images and no source change.
Four HIGH/CRITICAL gates and both package audits exited0 again. Earlier snapshots
are preserved under `security-final/scan-20261111` and `scan-20261112`; test
execution dates remain as recorded. This is not an absence-of-all-vulnerabilities claim.

API/web now use a minimal Debian runtime closure with original package/version,
license, NSS, CA and timezone data retained; no shell/package manager is shipped.
PostgreSQL uses patched official Alpine 18.6, nonroot from initialization. Redis
remains pinned 8.2.11. Independent final artifact review checked every manifest
hash/link, static ELF dependency and copied OS ELF metadata without starting a
container; it is separate from the actual runtime/browser/restore tests.

Remaining scanner package findings: API 54 medium/19 low/4 unknown; web
48 medium/19 low/4 unknown; PostgreSQL none; Redis one medium. These are package
findings, not unique exploit paths. The historical Debian HIGH/CRITICAL reports,
including CVE-2026-6653, are retained separately. The current Alpine advisory result
is not proof that every upstream libxml2 issue is fixed. No vulnerability-free or
complete vendored-binary coverage claim is made.

Fresh pip/npm audits report no known advisories in their package scope; they do
not replace the OS/image scans. The proposed remediation policy and all 149
lower-severity/unknown package findings are prepared in
`docs/security/REMEDIATION_POLICY_DRAFT.md` and
`docs/evidence/security-final/lower-severity-triage.json`. Accountable people,
first-detection ledger, accepted deadlines and hosted cadence remain unassigned.
No finding is silently accepted or given a fabricated due date.

## Open assessment and external conditions

The complete canonical ASVS source remains unchanged. The dated derived triage
has 126 BOUNDED_LOCAL_EVIDENCE, 57 NOT_ASSESSED, 119 EXTERNAL_NOT_VERIFIED and
43 NOT_APPLICABLE controls. Bounded evidence is partial, not a passed control.
The original 117/68/117/43 base assessment and defect reproductions are preserved.
Fresh action-time step-up, adaptive context controls and the broader L2/L3 local
backlog remain open; the two reproduced session defects are not still outstanding.

Public release still needs intended hosting/region/cost approval, real enterprise
OIDC/MFA, TLS/WAF/egress, secret/workload identity, private cloud bucket policy,
encrypted managed DB/backups, cloud restore/load acceptance, hosted CI, delivered
alerts, named on-call/release ownership, retention/legal review and release sign-off.
Local HTTP development, plaintext private backup files and recorded provider tests
do not satisfy those gates. Protect, live connectors and operational writes remain
disabled. Source was pushed to the user-authorized GitHub repository on 2026-11-14;
the application was not publicly deployed or connected to an airline. The source
upload does not change the dated test/advisory evidence or release verdict.

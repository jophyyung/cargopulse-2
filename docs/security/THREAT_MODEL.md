# CargoPulse threat model

Scope: synthetic Recover release candidate, architecture at `9a92fc1` and later
documented fixes. This is an engineering model with bounded test evidence, not an
external penetration assessment or aviation certification.

## Assets and trust boundaries

Browser input, uploaded JSON/CSV and identity-provider responses are untrusted.
The Next server guards console routes and proxies an explicit API method/path
allowlist. FastAPI authenticates each request independently; browser role labels
grant no authority. Server sessions retain a tenant prefix and a random secret;
only hashes are persisted. Privileges come from enabled local identity grants.

The non-owner PostgreSQL role cannot bypass row security. Each transaction sets
tenant context. Immutable source/plan payloads and append-only decisions/audit are
protected by database triggers and restricted grants. The schema owner, cloud
administrator and host administrator remain privileged trust boundaries; an audit
hash chain does not prevent their tampering or prove external non-repudiation.

The worker consumes stored hashes and immutable snapshots, not browser-supplied
solver results. Its DB lease owner fences terminal writes. Redis is only a hint
transport: all hints can disappear without deleting queued jobs. Private object
content is checked against the recorded SHA-256 before commit/work/approval.

The solver and the independent verifier are separate implementations. The latter
checks assignments, gates, aggregate physical resources, snapshot causality and
metric arithmetic/provenance. A mathematically valid synthetic envelope does not
establish real aircraft balance, packing, temperature continuity or clearance.

## Threats and implemented controls

- Cross-tenant identifiers and forged roles: server object predicates, local
  identity grants and PostgreSQL FORCE RLS; actual non-owner and API denial tests.
- Browser request forgery/session fixation: Origin plus session-bound CSRF,
  HttpOnly/SameSite cookies, per-authentication rotation/revocation and expiry.
  OIDC uses code/PKCE/state/browser binding/nonce, fixed issuer/audience/RS256,
  expiry/authorized-party validation and configured privileged MFA context.
  Verified context is persisted/rechecked after role changes; NULL/weak/stale
  contexts cannot gain privileged authority. Account disable transactionally
  deletes sessions under the shared tenant lock. Production cookie prefixes and
  stable read-only CSRF have explicit development/legacy transitions.
- Uploaded rule authority: an import must reference an exact registered published
  policy with authenticated independent review provenance. Only the explicitly
  enabled development profile accepts the fixed code-owned synthetic seed.
- Malformed input and file abuse: bounded JSON/multipart input, strict DTOs,
  controlled CSV format and formula neutralization, private content-addressed
  storage. The public web proxy also bounds chunked bodies and read deadlines.
  CSV filenames/extensions are constrained. Owned pinned-SDK XML protocol paths
  reject DTD and oversized/malformed responses; raw object blobs stay opaque.
- Duplicate/replayed decisions or work: idempotency keys, ETags, snapshot/plan
  hashes, current-source revalidation, DB uniqueness and fenced worker leases.
- Missing/replaced files and forged solver evidence: bounded SHA-256 reads,
  immutable payload hashes and independent physical/metric recomputation; invalid
  outputs are quarantined and cannot be approved or exported as verified evidence.
- Resource exhaustion: bounded input sizes/path enumeration/solver time, per-tenant
  pending-job quotas and worker-local tenant rotation. No global fairness or hosted
  capacity/SLA is asserted. API/IdP ingress rate controls still require deployment.
- Data leakage: server authorization on exports, private object adapter, no user
  URL fetcher, redacted allowlisted JSON logs/trace fields, production nonce CSP and
  no credential persistence in browser localStorage.
  The fixed-size client boundary marker contains only an epoch/state and one-way
  fingerprint; private DOM removal is not forensic erasure or server revocation.
- Unauthorised operational action: no airline write route or working airline
  connector exists. Startup rejects external-write/live/Protect flags. Human
  approval is an immutable in-app record, never booking/dispatch/load authority.

## Residual release conditions

Current exact-image HIGH/CRITICAL scans pass without ignores; remaining lower
package findings require triage and accountable policy acceptance. Old failing
reports remain historical evidence. The real IdP, TLS/WAF/egress controls, secrets manager, encrypted managed
database, private bucket policies, retention jobs, cloud backup recovery, delivered
alerts and operations ownership have not been supplied or verified. Local random
development passwords and private plaintext backup files do not satisfy those
production controls. Apply independent ASVS assessment and resolve these gates
before public publication.

The original ASVS 5.0.0 English CSV is preserved from the tagged OWASP source.
`ASVS-5.0.0-assessment.csv` triages all 345 controls with distinct dated notes:
126 bounded, 57 not assessed, 119 external and 43 non-applicable. The original base
triage and reproduced defects are preserved. BOUNDED_LOCAL_EVIDENCE means only the
named partial evidence was inspected/executed; broader remaining work stays open.
It is not ASVS compliance or a complete Level1 sign-off.

Source: [OWASP ASVS v5.0.0](https://github.com/OWASP/ASVS/tree/v5.0.0),
licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The preserved OWASP source and derived assessment CSVs are attributed to OWASP ASVS
v5.0.0 and made available under the same CC BY-SA 4.0 terms; assessment notes are
scoped engineering evidence, not an OWASP endorsement or compliance certificate.

# CargoPulse release gate

**Public L1 release: BLOCKED. Recover is implemented and running locally.
The final image HIGH/CRITICAL gate now passes; public release remains unapproved.**

Source was uploaded to the user-authorized GitHub repository on 2026-11-14;
see README.md for the source location. No public application deployment, airline
connection or operational write was performed. Protect remains disabled. The
original planning package and every reference PDF page were read before
implementation; canonical contracts and
11 tests were frozen before exact shared-worktree delegation.

## Current executed milestone

On 2026-11-12 (Hong Kong), the integrated security candidate passed **263 Python
tests**, zero failures/skips/xfails, in 87.16s with one upstream test-client
warning. Tests include real PostgreSQL/Redis, signed RSA with recorded OIDC
transport, true session/disable races, separate-process OTLP and the live web
boundary. The final deployed local images passed **14 Chrome tests** at
localhost:3000 (CLI: 1.0m), including the full 140-ULD Recover flow, decisions,
PDF, keyboard/viewports/axe and new session-privacy/header coverage.

After source commit `97cc22cfe7f3cd3b2e560b3c02555b0dbce3d2f2`, the lead
repeated the full suite from a clean exact Git worktree on 2026-11-12:
**263 passed, zero failures/errors/skips, 91.52s**, with the same upstream warning.
Imports resolved to that worktree, which stayed clean before/after. All31 running
Python files,45 web build inputs and packaging hashes matched that commit and the
same deployed image identities. Evidence: `security-final/clean-checkout` under
`docs/evidence`. Existing locked dependencies/isolated services were reused;
this is not new-host provisioning or another Chrome run.

Two independently reproduced session defects are fixed: weak authentication
cannot acquire privileged authority after local promotion, and disable/re-enable
cannot revive old sessions. Migration 0005 preserves legacy NULL assurance,
serializes creation/revocation and refuses unsafe downgrade. Cookie-prefix,
read-only stable CSRF, no-referrer/CSP, CSV filename, strict S3 protocol XML and
client private-DOM lifecycle changes have executed evidence. Some browser cases
explicitly inject failure/TTL/events/provider navigation; they are not live IdP,
native BFCache or actual full-session-lifetime acceptance.

All four exact runtime images pass actual Trivy HIGH/CRITICAL gates without
ignore/unfixed waivers. Lower findings remain: 103 medium, 38 low, 8 unknown
package findings across the images. Package metadata/SBOMs remain visible. The
API/web minimal runtime and patched Alpine PostgreSQL have actual build/runtime
and independent offline artifact evidence. See SECURITY_REVIEW.md.

On 2026-11-13, the same immutable images were rescanned with refreshed advisory
data and all four HIGH/CRITICAL gates still exited0. Refreshed pip/npm audits
reported zero known advisories in their package scopes. The current lower counts
above are103 medium/38 low/8 unknown package findings; no application source changed
and the 2026-11-12 test executions are not relabelled as new runs.

The original local PostgreSQL glibc-to-musl transition used a new volume and
logical restore. Fifteen table digests and private objects matched; old-volume
rollback was exercised before new writes. A separate fault probe proved accepted
new session/audit writes survive a post-start failure. The original volume and
private backups remain. Later ordinary 0004-to-0005 promotion preserved all other
table digests, legacy session values and private object hashes before new traffic.
Readiness requires schema0005; 12 tenant tables retain FORCE RLS and the app remains
nonowner/non-BYPASSRLS without directory-update rights.

The final actual Redis-outage/API/worker restart drill passed in 26.563s. A new
isolated schema0005 backup/restore matched all 15 tables and 11 private objects,
then cleared sessions/transient work and made proposals stale without changing
historical decisions/audit/snapshots/policies. An actual ASGI app using the restored
DB and a separate restored-object volume read 11 scenarios and blocked 23 stale
plans across both tenants. These local exercises are not managed PITR/cloud RPO/RTO.
See RESTORE_DRILL.md and `docs/evidence/24-security-remediation.md`.

## Historical evidence retained with its original scope

The 585 complete native synthetic benchmark plans all passed independent physical
and metric verification: 450 mixed plans and 135 negative controls. They were
recorded on 2026-11-10 and were not rerun on the new images. Optimizer/verifier
source is unchanged; the benchmark is not hosted/cold/concurrent performance or
an SLA. The four current metrics retain ADR-006's proposal-only scope.

The earlier independent clean-volume installation at e40c676/schema0004 and final
third-layer numerical review remain valid historical bounded evidence. They are
not silently relabelled as reviews of the new authentication/frontend source.
Final runtime artifact review is in evidence22. The exact-image second-person
fresh-volume install in evidence23 passed schema0005/nonowner/RLS, a real8-ULD
HTTP journey, known-ID tenant denials, byte-identical exports across restart and
one Chrome supplement. That operator authored the frontend boundary; the latter
is execution evidence, not independent review of their own frontend security.
Earlier failures/incomplete attempts remain recorded and are not counted as passes.

## Conditions required before publication

1. Complete owner/security acceptance of the ASVS-based triage and proposed
   remediation policy, including remaining local controls and all lower findings.
   A passing image gate and 345-row inventory are not ASVS compliance.
2. Approve intended hosting, region, registry, domain and costs; verify external
   availability, TLS, firewall/WAF and egress on that infrastructure.
3. Accept actual enterprise OIDC/MFA and approved grants. Production enables no
   default development identities and must not carry local development sessions.
4. Verify encrypted managed DB/backups, private object policies, secret/workload
   identity, intended-environment load and isolated cloud recovery.
5. Deliver monitoring/alerts to named on-call owners; accept retention/privacy/
   terms/licensing/legal review, release ownership and signed release decision.
6. Execute hosted CI and intended-environment deployment acceptance. Local
   actionlint/Compose/build/tests do not establish hosted CI green.

The concrete production Compose/runbook still requires approved immutable images
and external settings, with all operational writes disabled. Only its reserved-
placeholder configuration parsing is exercised locally. No paid service was
created. Original red-line gates in `ops/02_RELEASE_GATES.md` are unchanged.
L2/L3 require separate data/domain/operational authorization and are not approved.

## Source and agent honesty

Application authentication/storage/frontend source has changed since e40c676.
`docs/evidence/runtime-source-hashes.json` binds all 31 running Python source files,
45 web build inputs and packaging hashes to the final API/web image identities;
contracts and optimizer/verifier algorithms remain unchanged. The authorized
GitHub source handoff retains the existing history on `main`; local runtime,
credentials and private backups remain ignored by Git. This source upload does
not satisfy the pending hosted CI, deployment or release-acceptance gates.

Requested second-layer gpt-6.1-sol/high settings were used for delegated work.
Earlier third-layer numerical work used the requested setting; a later Luna
coverage attempt returned Bad Request and delivered no review. The lead model
cannot be changed/verified by a chat instruction or tool, so no claim is made
that it was switched to gpt-6.1-sol/max. Executed artifacts/tests bind the work.

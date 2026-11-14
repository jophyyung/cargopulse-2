# Control-by-control ASVS local review

Historical base review: the counts and CP-ASVS-001/002 reproductions below describe
the inspected base, not the later corrected application. Root remediation and
new executed evidence are recorded in `24-security-remediation.md` and
`security-final/asvs-coverage-after-remediation.json`. The original derived CSV is
preserved as `asvs-review/assessment-base.csv`; the current assessment includes
explicitly dated follow-up notes. Neither assessment is a compliance certificate.

Review started: 2026-11-11. Triage/coverage completed: 2026-11-12.
Application source reviewed: local worktree base
`1b003eb22427c784fe1b59fff6bfe650be120909`. Scope: the proposal-only, synthetic
Recover application, its security architecture, implementation and existing test
evidence. This is a complete **345-control applicability/evidence triage**, not
ASVS compliance, a penetration test, a complete Level 1 sign-off or production
acceptance. Every canonical control has a distinct review note.

Only `docs/security/ASVS-5.0.0-assessment.csv` and this report are new changes for
this task. Application/contracts, root workspace services/data and canonical
vendor CSV were not modified. No service, database role, native database reset,
remote push or public deployment was performed.

## Canonical source and status interpretation

The preserved seven-column source contains 345 requirements across V1-V17. The
review downloaded the tagged OWASP v5.0.0 English CSV again and verified it is
byte-for-byte identical to `docs/security/ASVS-5.0.0-source.csv`, SHA-256
`98c8fe911b9edb403af8ee05d3ce8201ecac2659e313b053890a62847cdcf680`.
All seven vendor columns, requirement order, IDs, descriptions and levels remain
unchanged in the derived assessment. The nine-column assessment schema is retained.

The existing status vocabulary is retained:

- **BOUNDED_LOCAL_EVIDENCE: 117.** Relevant implementation and/or recorded local
  tests were inspected. Notes distinguish inspection from executed tests and
  identify partial coverage. This means there is bounded evidence for the named
  portion; it is not a claim that the entire control passes. These rows may still
  contain local or external remaining work.
- **NOT_ASSESSED: 68.** The requirement has now been read and triaged, but the
  required local behavior/verification is not established. This retained label
  covers confirmed local gaps and tests/design still needed. It no longer means
  that the reviewer skipped reading the requirement.
- **EXTERNAL_NOT_VERIFIED: 117.** Intended-environment, IdP, hosting, key custody,
  operations, retention/legal or accountable-owner evidence remains necessary.
  An application-side partial control does not clear the external dependency.
- **NOT_APPLICABLE: 43.** A specific conditional mechanism or feature is absent
  from the declared application boundary, with a reason in every row. It is not
  used for a necessary security capability that simply has not been implemented.
- **DELEGATED_UNVERIFIED: 0.** The vocabulary remains valid, but no row relies on
  an unfinished delegated assessment in place of its actual local/external status.

There are **302 applicable controls**. No compliance percentage or pass count is
derived from the status totals. Existing low/medium image advisories, lack of a
documented remediation schedule and the independent external release conditions
are not waived by the newly passing HIGH/CRITICAL image gate.

The non-applicable boundaries are concrete: no LDAP/XPath/LaTeX/JNDI/memcache/mail
query feature; no user HTML/SVG/style-language interpreter; no archive/image
upload decompression; no GraphQL/WebSocket/SAML/WebRTC/TURN/media signaling; no
OAuth access-token resource-server API; no multi-issuer client selection or OIDC
back-channel logout parser; no password-derived application encryption keys; no
externally hosted client assets. The app still requires working user identity,
MFA, recovery, session lifecycle, transport, retention and operations controls.
Those are not made non-applicable by delegating them or by using synthetic data.

## Newly executed defect reproductions

Both tests use an isolated SQLite in-memory application and private temporary
object directory. They do not connect to PostgreSQL/Redis or the running workspace.
The OIDC reproduction uses real RSA signatures with recorded provider transport;
it is not a real IdP acceptance test. A test marked passed below means that the
defect was successfully reproduced, not that its security control passed.

**CP-ASVS-001: an existing low-strength session gains privileged authority after
local role promotion.** SEC checks the required `acr` only at OIDC login, while
`authenticate()` later reloads current local roles without retaining/rechecking
the session's authentication strength. The test first logs in a `load_analyst`
with `acr=password-only`, observes policy-draft POST denied with 403, changes its
local role to `manager`, then uses the same cookie to create a policy draft with
201. Only one token exchange occurs; no reauthentication occurs. Root was
immediately notified. Relevant controls include V6.8.4, V7.5.3 and V8.2.4.

Command executed:
`python -m pytest .local/asvs-review/test_mfa_role_transition.py -q -s`.
At that time the file contained only the role-promotion reproduction:
**1 passed, 1 upstream TestClient deprecation warning, 1.75s**.

**CP-ASVS-002: account re-enablement revives its old session.** Disabling
`Identity.enabled` makes the existing cookie return 401, but setting it back to
true restores 200 without a new login. The base code suspends use rather than
terminating the session. Root was immediately notified and V7.4.2 is marked as a
confirmed local gap. Disabling an account needs an irreversible revocation event
or equivalent lifecycle enforcement; an ordinary enabled-state check is insufficient
to establish termination.

Command executed:
`python -m pytest .local/asvs-review/test_mfa_role_transition.py -k disabled -q -s`:
**1 passed, 1 deselected, 1 upstream warning, 1.94s**.

Raw commands/results and the reproducer remain under ignored `.local/asvs-review/`:
`test_mfa_role_transition.py`, `mfa-role-transition.txt`, and
`disabled-session-revival.txt`. This task does not claim that either defect has
been fixed. Root may remediate them independently; update the affected rows only
after linking the exact fixed source and new regression/runtime evidence.

## Level 1 local priorities

Exactly **9 Level 1 requirements** remain NOT_ASSESSED at this reviewed base.
These are a prioritized verification/remediation list, not nine demonstrated
exploitable vulnerabilities:

- **V7.4.2: confirmed session defect.** CP-ASVS-002 has an actual isolated
  disable/re-enable reproduction. Ensure database/operator account disable paths
  invalidate prior sessions permanently, then test raw SQL and application paths.
  Keep this row open until the fixed source and successful regression are linked.
- **V3.3.1: directly verified configuration gap.** A pure production-mode
  `session_cookie()` response constructed a Secure/HttpOnly cookie named
  `cp_session`, without the required host/secure prefix. The raw header is in
  `.local/asvs-review/production-cookie-probe.json`. This probe did not run a
  server/browser or demonstrate a cookie-tossing exploit. Fix and test the
  production naming/path/domain transition and deliberate development exception.
- **V14.3.1: source-observed lifecycle gap.** Logout navigates after a successful
  API response; failure retains the console and there is no explicit cross-tab
  or offline clearing handler. Verify expiry/logout/offline/back-button behavior
  in a browser and implement sensitive-state clearing as required.
- **V3.5.3: source-observed safe-method mutation requiring evaluation.**
  GET `/auth/csrf` rotates stored `csrf_hash`. Test concurrent requests and
  cross-site initiation before claiming a browser-based denial or forgery defect;
  rotating a token alone does not demonstrate that exploit.
- **V5.2.2: source-observed policy gap.** Controlled CSV content/MIME is parsed
  strictly, but upload extension is not explicitly checked. Define permitted
  filename behavior and test mismatches; this is not evidence that uploaded code
  executes or that arbitrary file contents are accepted.
- **V1.5.1: missing SDK parser evidence.** No user XML upload exists, but botocore
  parses S3 service-protocol XML. Review the pinned parser's DTD/entity handling
  and add malicious protocol-response tests. No XXE defect was demonstrated.
- **V14.2.1: missing callback leakage evidence.** OIDC code/state in the callback
  URL are normal protocol inputs. Verify callback log/referrer redaction and
  unrelated secret-in-URL rejection; the normal query parameters are not by
  themselves a product defect. Actual edge log policy still needs owner input.
- **V15.1.1: missing accountable policy.** Agree severity-based remediation and
  general update deadlines, scan cadence and owners. This can be documented
  locally but requires an accountable owner to accept the deadlines.
- **V15.2.1: missing policy-to-build reconciliation.** Reconcile the current raw
  image/dependency findings, including lower severities, against those deadlines.
  A HIGH/CRITICAL gate pass alone cannot prove compliance with a nonexistent
  remediation schedule.

CP-ASVS-001 remains a separately reproduced local defect in Level 2/3 controls;
it is not omitted merely because the priority list above filters Level 1.
Root is independently remediating both defects. This base triage does not mark
them fixed in advance and does not expand the task into implementing all L3 controls.

## Remaining work that can be done locally

The individual CSV notes are the authoritative control-specific backlog. These
groups identify concrete implementation/test work rather than repeating a generic
inventory disclaimer:

1. **Session assurance and lifecycle.** Fix/retest both reproduced defects.
   Define inactivity, absolute-age and parallel-session policies; implement idle
   expiry, audited administrator revocation and reauthenticated self-service
   session inventory/termination. Test promotion, demotion, disable/re-enable,
   factor-change events and stale authentication context. Relevant rows include
   V6.8.4, V7.1.1-V7.1.2, V7.3.1, V7.4.2-V7.4.3, V7.4.5, V7.5.2-V7.5.3 and V8.2.4.
   Real provider factor events and risk thresholds still need owner input.
2. **Browser isolation and sensitive state.** Add/test the intended production
   host-prefixed cookie design; resolve CSP `base-uri` and response coverage;
   decide COOP, CORP/Sec-Fetch and violation intake behavior; test logout/expiry,
   offline state, multiple tabs and back/forward cache clearing. Document browser
   requirements and safe failure behavior. V3.3.1/V3.3.3, V3.4.3/V3.4.6-V3.4.8,
   V3.5.3/V3.5.8, V3.7.3/V3.7.5 and V14.3.1 remain open locally.
3. **Abuse and resource budgets.** Pending-solve caps do not replace authenticated
   import/export/auth-start rate limits, user/tenant storage/file quotas or global
   admission control. Define atomic quota/orphan cleanup behavior, connection
   pools/retries/cancellation and mixed-tenant starvation tests. See V2.1.3,
   V2.4.1-V2.4.2, V5.2.4, V13.1.2-V13.1.3, V13.2.6 and V15.4.4.
4. **Interpreter/parser boundaries.** Add duplicate JSON/query/header/cookie/form
   tests, Unicode/percent encoding agreement, bool/int/string coercion and
   prototype-key payloads. Exercise HTML/JSON/URL/PDF output contexts, CSV
   tab/null/formula leading characters and roundtrips. Include filename/extension
   mismatches and a documented constrained-upload malware disposition. See
   V1.2.10, V1.5.1/V1.5.3, V5.2.2/V5.4.3, V15.3.5-V15.3.7 and partial V1/V3
   rows. S3 SDK XML response parsing still needs entity/DTD review even though
   there is no user XML upload feature.
5. **Direct HTTP/configuration exposure.** Test all methods including TRACE,
   direct API docs/OpenAPI/health audience, oversized headers/cookies/query,
   attachment media types, content-length/streaming responses, cache deception,
   static/dotfile/source-map/config disclosure and server-version headers. See
   V4.2.2/V4.2.5, V13.4.3-V13.4.7 and V14.2.5. Real HTTP2/3/edge parser agreement
   remains external rather than simulated by these local tests.
6. **Authorization documentation and field minimization.** Complete an explicit
   endpoint/role/read-write field matrix and document contextual attributes,
   thresholds and sensitive-action step-up. Test every response projection and
   worker's originating-subject authority, not only an IDOR example. See
   V8.1.2-V8.1.4, V14.2.6 and the remaining work in V8/V15 bounded rows.
7. **Cryptographic and dependency inventory.** Document actual crypto call sites,
   algorithms, key use and migration paths; define accepted issuer key sizes and
   negative tests, RNG failure behavior and scoped timing/exception analysis.
   Complete native/risky-component/dangerous-function catalogs, registry/index
   allowlists, native optional-package provenance and risk-based remediation
   deadlines. See V11.1.2-V11.1.3, V11.2.2/V11.2.4/V11.5.2 and V15.1/V15.2.
   Key custody, managed encryption and accepted crypto policy are external.
8. **Security-event completeness.** Add safe unauthenticated authentication
   failure/factor/reason events, complete the validation/authorization/abuse event
   matrix, and fault-test IdP/JWKS/S3/TLS/unhandled-error paths without secrets.
   Confirm CR/LF-safe downstream consumption and correlation fields. V16.3.1,
   V16.3.3-V16.3.4 and the partial V16 rows require more than generic HTTP counts.
   Delivered monitoring and immutable log custody still require external owners.

Absence of shell/package managers in the reviewed minimal images is a verified
artifact property, not proof of all these security behaviors. Likewise, code
inspection, a permissive test fixture, or one rejection test cannot establish an
entire ASVS requirement.

## Necessary owner and intended-environment inputs

- **Identity owner:** approved IdP/client registration, supported factors and
  authentication strengths, user password/recovery/enrollment policy, factor
  loss/renewal/revocation, notification/consent controls, key/algorithm policy,
  RP/IdP session and logout coordination, and real MFA/PKCE/code-replay evidence.
  Optional provider mechanisms require explicit enabled/disabled configuration,
  not an assumption that CargoPulse's local OIDC tests cover them.
- **Hosting/security owner:** approved region/domain/cost and exact registry
  digests; TLS versions/ciphers/certificate revocation/HSTS/ECH feasibility;
  trusted proxies and protocol boundaries; authenticated/encrypted internal
  service traffic; egress allowlists; workload identity/vault/least-privilege IAM;
  encrypted database/object/backup policies, rotation and managed restore drills.
- **Operations owner:** log inventory/access/retention, clock synchronization,
  separate tamper-resistant collection, alert delivery/escalation/on-call,
  capacity/fairness expectations and remediation deadlines with accountable roles.
- **Data/legal/product owner:** real field classifications/minimization,
  provenance/metadata consent, retention/legal holds/deletion/backup expiry,
  privacy/terms approval, browser policy and risk-based session/action assurance.
  Synthetic operational data does not remove the need to protect real identity
  and administrative data.

No infrastructure or provider policy was invented to fill these inputs. Their
rows remain EXTERNAL_NOT_VERIFIED even when code is prepared for the integration.

## Evidence references and limits

To keep individual CSV notes short, these aliases resolve to repository paths:

- API, SEC, CONFIG, DOMAIN, STORE and OBS:
  `services/api/cargopulse_api/main.py`, `security.py`, `config.py`, `domain.py`,
  `storage.py` and `observability.py`, respectively.
- MODEL: `packages/contracts/python/cargopulse_contracts/models.py`.
- WEB: `apps/web/src/`, plus `apps/web/next.config.ts`; SERVER:
  `apps/web/src/lib/server.ts`; CONNECTORS:
  `services/api/cargopulse_api/connectors.py`.
- OPTIMIZER and VALIDATOR: `services/worker/cargopulse_optimizer/` and
  `services/worker/cargopulse_validation/`; DB:
  `services/api/cargopulse_api/db.py` and `tables.py`.
- CONTRACTS: `docs/CONTRACTS.md`; IDENTITY_ADR:
  `docs/adr/0003-identity-and-read-only.md`; PRODUCTION:
  `docs/PRODUCTION_DEPLOYMENT.md`; QA08:
  `docs/evidence/08-qa-remediation.md`; RUNTIME_REVIEW:
  `docs/evidence/14-minimal-runtime-review.md`; DEPENDENCIES:
  `docs/DEPENDENCIES.md`; THREAT_MODEL: `docs/security/THREAT_MODEL.md`.
- Named `test_*` functions resolve to `tests/backend/`, `tests/release_qa/`,
  `tests/contracts/`, `tests/optimizer/`, `tests/validation/` and
  `tests/observability/`. Every explicitly named function was checked to exist;
  their source/recorded outputs were reviewed, not rerun wholesale for this task.

The lead separately reported a current 180-test/79.30s Python run, four actual
runtime image HIGH/CRITICAL gates passing, and a 29.817s logical migration/rollback
with all 15 tables, 8 objects and 12 FORCE RLS tables preserved. The current root
`docs/evidence/security-summary.json` was read and binds API `6965d4eb...`,
web `0fa03daf...`, PostgreSQL `07b174247...` and the pinned Redis image. These are
separate lead/runtime evidence, not new executions by this ASVS reviewer. The base
worktree's older security/release prose still describes historical image blockers;
integration must retain the history while updating current conclusions precisely.
Neither image gates nor migration success proves the remaining ASVS controls.

Machine evidence under ignored `.local/asvs-review/` includes the final
`coverage-validation.json`, source/report hashes, tagged vendor CSV, the two
defect reproductions/logs and authored-value/preview checks. All 345 rows have
nonempty unique notes; no placeholder independent-assessment sentence remains.
An authorized `gpt-6-luna/max` coverage-only subagent attempt returned `Bad Request`
without delivering checks. It is not counted as a completed third-layer review; the author
performed the listed coverage checks directly. No complete penetration exercise,
hosted CI run, intended-environment acceptance or external owner sign-off is claimed.

## Attribution

The canonical requirements are OWASP Application Security Verification Standard
v5.0.0, available from the
[official tagged English CSV](https://raw.githubusercontent.com/OWASP/ASVS/v5.0.0/5.0/docs_en/OWASP_Application_Security_Verification_Standard_5.0.0_en.csv)
and [OWASP ASVS project](https://asvs.owasp.org/). The preserved source and derived
assessment retain [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
attribution/terms. These engineering notes are not OWASP endorsement or certification.

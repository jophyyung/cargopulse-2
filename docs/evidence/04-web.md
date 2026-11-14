# Web implementation evidence

Status: implementation and standalone login checks complete; authenticated Recover
integration verification is pending the API/worker integration. Not an L1 release,
production OIDC acceptance, operational validation or user visual acceptance.

## Scope and contracts

Owned paths: `apps/web/` and this report. Shared baseline was
`a8192318fcdbf72faac72838fe2d1a0de0c9b7b2`; lead-approved runtime contracts
`13476a199a8fd9175de0f5ebfd49c89e11ec6875` were applied as `fadbc22` in the isolated
frontend worktree. Generated `components['schemas']` types are imported from
`packages/contracts/generated/api.ts`; no frontend DTO or root configuration was
changed. Lead owns the final root lockfile regeneration.

Implemented a Next.js Node application using pinned Next.js 16.4.6, React 19.3.1,
TypeScript 6.0.3 and Node 24.14.x. The standalone build includes a bounded,
fixed-origin API proxy, server `/me` route guard, cookie sessions, original-Origin
forwarding, CSRF echo, new idempotency keys and server-supplied quoted ETags.
Production development-login access is disabled unless explicitly enabled by
`CARGOPULSE_ENV=development`. No credentials enter browser storage.

Real API workflows: source fixture/JSON and controlled CSV validation/commit;
immutable scenario creation/supersession; manifest, quality, accepted/excluded
paths, routes/cutoffs and server-computed urgency; asynchronous solve and durable
job polling; actual plan/baseline/metric inspection; reason, full-hash acknowledgment
and typed approval/rejection/escalation; decision receipt; permissioned plan reports
(JSON/CSV/PDF); scoped audit; published policies and independent manager draft review.
The manager-reviewer development identity is explicitly marked development-only.

English and Traditional Chinese labels and cookie-persisted locale are included.
Protect and external integrations display unavailable/not-connected states. Every
workspace retains SYNTHETIC / NOT CONNECTED and in-app decision boundaries. No
operational fixture responses, metrics, urgency values or graph series are invented.
Metric labels distinguish proposed first-flight departure within 48 hours from
physical arrival or confirmed re-protection, and eligible/all-affected denominators.

## Actual verification

- `npm install --ignore-scripts`: exit 0; 68 packages audited, 0 vulnerabilities
  reported at this installation. This is not a complete supply-chain audit.
- `npm run typecheck --workspace apps/web`: exit 0.
- `NEXT_TELEMETRY_DISABLED=1 npm run build --workspace apps/web`: exit 0 after the
  final feature changes. Next.js reported all 15 page/route entries as dynamic and
  the request Proxy active. Compilation, TypeScript and standalone tracing passed.
- Started the generated standalone Node server after copying `.next/static` into
  its standalone application directory. This tested the output artifact, not only
  the development server.
- `CARGOPULSE_BROWSER_CHANNEL=chrome node apps/web/tests/login-smoke.cjs`: exit 0
  against that optimized standalone output. Four viewports: 1280×720, 1440×900,
  1920×1080 and 768×1024. No document horizontal overflow; login heading visible;
  English/Traditional Chinese switch and locale survived reload. Four requests
  produced different CSP nonces, every script carried a nonce, production script
  policy had neither unsafe-inline nor unsafe-eval, and no page/CSP errors were
  observed. An arbitrary proxy route returned 404.
- Screenshots and machine-readable scope/results are in `apps/web/evidence/`.
  The 1440 screenshot was visually inspected. Login screenshots do not validate
  authenticated tables, charts, decision interactions or operational quality.
- Applied the React best-practices review: independent reads start in separate
  abortable effects; mutation sequencing follows server dependencies; no unsafe
  HTML or client-side privilege authority; native labelled forms, table captions,
  sticky table headers, keyboard focus rings, roving arrow-key tabs, reduced-motion
  support and textual chart/table alternatives. This is a source review, not a
  WCAG conformance audit or assistive-technology test.

The bundled Playwright Chromium executable was absent. The first bundled-browser
launch failed with its missing-executable error. The installed Chrome channel was
then used successfully; no browser download or production response mock was used.

## Remaining integration and acceptance

- `apps/web/tests/recover.spec.ts` is a real-service Playwright flow for login,
  fixture validation/commit, scenario/candidate/urgency review, durable solve,
  independent PASS, in-app approval and audit. It has not yet run successfully:
  no API was reachable at local port 8000 during this frontend handoff.
- Lead must run authenticated review at all target desktop sizes, role switch,
  controlled CSV error paths, forced job failure/reconnect, approval conflicts,
  cross-tenant denial, rejection/escalation, independent two-manager publication,
  guarded JSON/CSV/PDF reports and OIDC against the integrated stack. UI controls
  and API wiring alone do not establish those operations working.
- Published policies cannot be reverted in this build. Protect, connectors,
  external writes and historical replay distributions remain unavailable.
- Metrics and audit-page JSON exports represent already authorized returned
  records. They do not create a benchmark cohort, confidence interval or physical
  operational outcome. Runtime percentiles remain absent without a real cohort.
- The source-level CSP uses fresh 256-bit per-request script nonces. Inline styles
  remain allowed. Actual deployment TLS, HSTS, network egress, secrets manager,
  reverse-proxy limits and full security/accessibility review remain release gates.
- Hosting, production SSO/MFA, retention/legal approval and user acceptance are
  outside this local verification. No airline system was connected or mutated.

## References and rollback

Checked official Next.js documentation for [standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output),
[Route Handlers](https://nextjs.org/docs/app/api-reference/file-conventions/route)
and [nonce-based CSP](https://nextjs.org/docs/app/guides/content-security-policy).
Next.js/React use MIT licences; TypeScript uses Apache-2.0. No icon library,
third-party fonts, analytics or external rendering service was added.

Rollback is a frontend image/commit rollback; no storage migration is included.
Do not remove immutable backend decisions when rolling back the UI.

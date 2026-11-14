# CargoPulse web client

Next.js 16.4.6 / React 19.3.1, Node 24.14.x. This is a server application,
not a static export. Every operational record comes from the private API;
there are no production mock responses, fabricated metrics or browser access tokens.

Run workspace commands from the repository root after `npm ci`:

```sh
npm run typecheck --workspace apps/web
npm run build --workspace apps/web
CARGOPULSE_ENV=development API_INTERNAL_URL=http://127.0.0.1:8000 npm run dev --workspace apps/web
```

`API_INTERNAL_URL` is a server-only HTTP origin, defaulting to
`http://127.0.0.1:8000`. The fixed `/api/v1` proxy allowlists enabled routes and
forwards cookies, original Origin, CSRF, ETags, status and Set-Cookie. No arbitrary
proxy target can be supplied by the browser. Commands generate an Idempotency-Key
and correlation reference. Server layouts check `/me`; the API remains the
permission authority for every object and action.

`CARGOPULSE_ENV=development` explicitly enables the fixed local identity selector
and development login proxy. It must remain unset or be `production` in deployed
production. This option is independent of Next.js `NODE_ENV`: the local integration
can exercise an optimized production build while clearly displaying development
identities. Never describe that as a production OIDC login.

For a standalone image built from the monorepo root, copy `.next/static` into
`.next/standalone/apps/web/.next/static`, and public assets into the corresponding
`public` directory. Start `node .next/standalone/apps/web/server.js`. The lead-owned
Dockerfile packages these assets. An output trace root includes the monorepo.

A request proxy generates fresh 256-bit CSP nonces. Pages render dynamically and
cannot be publicly cached. Production scripts allow neither unsafe-inline nor
unsafe-eval. Development eval is limited to `NODE_ENV=development`. Inline styles
remain allowed. No external fonts, analytics, map tiles or brand artwork load.

## Workflow

A Data steward or Manager loads service fixtures, validates JSON or controlled
CargoUnit CSV, then commits an immutable source. A Controller or Manager creates
a scenario, reviews manifest, quality findings, candidates, excluded arcs,
source cutoffs and server-computed urgency, requests a durable solve, polls its
persisted ID and opens the independently validated proposal. A newer committed
source can supersede a scenario without overwriting old plans.

The decision sheet shows actual assignments, unassigned units, baseline records,
metric denominators and solver telemetry. Decisions require full-hash acknowledgment,
a reason and typed action confirmation. The service's approvable flag, blockers,
current snapshot, independent validation and quoted ETag are respected. A receipt
confirms only an in-app decision. Protect and airline integrations remain disabled.

Published policy records are immutable. Managers can draft and load a policy for
review; an independent Manager publishes it. A server-loaded draft is required
before the publish confirmation is shown. English and Traditional Chinese locale
preferences persist in a non-sensitive cookie. UTC is canonical; the route table
can display selected local zones and always retains exact UTC in timestamp titles.

Reports are downloaded from the permissioned API in JSON, CSV or PDF. Evidence and
audit-page JSON downloads export only data already returned to the current session,
with a synthetic label and provenance; they are not new benchmark measurements.

## Verification

No test below uses mocked operational responses. A running API, PostgreSQL and
worker are required for the Recover integration test. Tests mutate synthetic data.

```sh
CARGOPULSE_E2E_URL=http://127.0.0.1:3000 npx playwright test -c apps/web/playwright.config.ts
```

For an installed Chrome instead of Playwright's bundled Chromium, add
`CARGOPULSE_BROWSER_CHANNEL=chrome`. A login-only smoke script can run without the
backend against an optimized standalone server. It verifies CSP nonces, four
viewports, locale persistence, a fixed proxy boundary and page/CSP errors:

```sh
CARGOPULSE_E2E_URL=http://127.0.0.1:3100 CARGOPULSE_BROWSER_CHANNEL=chrome node apps/web/tests/login-smoke.cjs
```

See `docs/evidence/04-web.md` for actual results and limits. Build/type checks or a
login smoke test do not establish authenticated end-to-end operation, accessibility
certification, user acceptance, production OIDC, hosting or operational effectiveness.

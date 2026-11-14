# Client session boundary candidate

Date: 2026-11-12. Base: `1b003eb22427c784fe1b59fff6bfe650be120909`.
Branch: `codex/browser-session-hardening`.

Status: **implemented; TypeScript and production build verified; matching-stack
browser acceptance pending**. This is bounded work for ASVS V14.3.1. It does not
establish complete ASVS compliance, intended-environment identity acceptance or a
public release.

Only frontend code, a new Playwright test file and this report were changed. No
backend, contracts, assessment CSV, root service, native database, database role or
existing volume was modified. No service was started for browser acceptance, and
no commit, push or deployment was performed.

## Behavior implemented

`Shell` starts with a public verification view and does not mount its private
console subtree until its client session check succeeds. The existing server
layout still verifies the principal; backend authentication, authorization and
role checks remain authoritative. The client state is a privacy/UX boundary and
cannot grant access.

The following events synchronously replace the mounted console with a public
view, removing its forms, account display and private children rather than merely
hiding them with CSS:

- A sign-out attempt, before the CSRF read or logout network request.
- A 401 received by the application API wrapper or export download wrapper.
- A browser `offline` event.
- A boundary notification from another tab, delivered through the application's
  own localStorage key.
- A persisted `pagehide` or `pageshow` event, covering the BFCache lifecycle
  handlers. Pagehide redaction is intended to precede a retained-page snapshot.

Startup, focus and becoming visible recheck the server session. The check requires
a valid non-sensitive `X-Session-Expires-In` header from the server. It establishes
a monotonic client deadline from request initiation plus the reported seconds,
subtracting the whole request/processing round trip conservatively. Shell then
sets a redaction timer: an idle foreground document needs no new API request,
focus event or server-side session renewal to remove its private subtree at that
deadline. Zero closes immediately; missing, malformed, negative, fractional or
out-of-timer-range metadata fails closed. The accepted timer range is at most
2,147,483 seconds, avoiding browser timeout overflow.

Each successful verification replaces the old client timer with the newly
reported remaining lifetime; it does not extend the server session. Redaction
and component cleanup clear the timer, and cleanup cancels verification requests.
A response from before another tab's session change cannot reopen its old subtree.
The conservative timer may close slightly early, so the public message requests
fresh verification rather than falsely claiming that server logout was confirmed.

Public messages are English/Traditional Chinese and contain no principal, tenant,
role, incident or draft data. A successful logout message requires the real
endpoint to return HTTP success with JSON `revoked: true`. A failed request or
offline event leaves an explicit unconfirmed message. The user can retry sign-out
manually or start a fresh sign-in. There is no queued logout, automatic replay or
background revocation claim. Requests already accepted by the backend cannot be
cancelled or undone by client DOM removal.

## Fresh sign-in and persisted state

The client stores only `cargopulse.session-boundary.v1`, containing a version,
random epoch, a one-way SHA-256 fingerprint and numeric state. The fingerprint is
derived from the server's per-session CSRF value; no raw CSRF/authentication token,
principal, role, path, draft or cargo data is stored in localStorage or
sessionStorage. The record reserves a fixed byte size before private UI is shown,
so subsequent boundary writes replace the same-size record even under ordinary
storage quota pressure. If required storage or Web Crypto cannot be used, the
candidate keeps the private UI unmounted. It does not clear unrelated storage.

A locked session cannot reopen just because the browser reconnects, reloads or
revisits an old route. Recovery requires one of these server-confirmed transitions:

- An explicit development sign-in succeeds, its new session is checked, and a
  full-document navigation discards the previous console view.
- Organisation SSO preflight records the old session fingerprint, then navigates
  to the existing backend login endpoint. On the callback's normal full-document
  return, a changed server-verified fingerprint permits the new session. This
  path is independent of the principal's `auth_mode`; it is not a development-only
  reset helper. Abandoning SSO with the original cookie leaves the view locked.
- If that explicit SSO preflight receives a server 401, it records the absence of
  an accepted session. A later accepted session can then mount after the callback.
  Transport failure is not treated as that 401 confirmation.

Other tabs that already redacted do not automatically remount when a sign-in
updates the shared marker. They require an explicit navigation/recheck. The
fingerprint and marker are not authorization credentials, and backend checks
continue to apply if a browser user manually edits or clears them.

This does not promise forensic erasure of JavaScript memory, browser caches,
already loaded framework/RSC transport data or previously downloaded files. The
implemented claim is removal of the mounted private console DOM. True browser
BFCache admission/restoration timing and supported-browser behavior still require
the runtime checks below.

## CSRF integration dependency

Every authenticated POST now first fetches `/api/v1/auth/csrf` with same-origin
credentials and `cache: no-store`, reads JSON `csrf`, and sets `X-CSRF-Token`.
Anonymous `/auth/development` skips this pre-session step. The helper does not read
`document.cookie` or depend on `cp_csrf` versus `__Host-cp_csrf` naming. Response
401 handling also applies to the CSRF read itself.

**Integrate with the new backend stable per-session, read-only HMAC CSRF endpoint.**
The base backend rotates CSRF on GET and is not a valid acceptance target for the
fingerprint mechanism. A rotating GET would misidentify an old session as fresh.
The public CsrfToken DTO remains unchanged. This frontend task does not implement
or claim the backend change, cookie-prefix hardening or authentication-strength
and account-disable fixes.

The Next API response-header allowlist must also forward `X-Session-Expires-In`.
That header wiring is owned by the lead's separate header patch and is not changed
by this worktree. Without it, the client intentionally remains closed. The lead
reported two backend metadata tests covering no renewal and no expiry header on
expired-session 401; those are separate backend evidence, not executions here.

## Verification actually executed

Using the existing Node 24.22.2 toolchain and isolated copies of the root's
read-only dependencies:

- `npm run typecheck`: **PASS** on the final source.
- `npm run build`: **PASS**, real Next.js 16.4.6/Turbopack production compilation,
  TypeScript, page-data collection, static-page generation and final optimization.
- `playwright test --config apps/web/playwright.config.ts --list apps/web/tests/session-boundary.spec.ts`:
  **8 tests discovered**. Listing is not test execution.
- `git diff --check`: **PASS**.
- The React quality review checked conditional unmounting, server/client trust
  boundaries, event subscription cleanup, request cancellation, stale-response
  races, public-view semantics, accessible controls, strict TypeScript and absence
  of new dependencies. This inspection is not browser acceptance.

The first build failed because Turbopack could not resolve a dependency symlink
outside the worktree root. An intermediate retry saw an incomplete dependency
copy. Both outputs are preserved. The final build used a completed, real ignored
`node_modules/` directory inside this worktree and succeeded without changing
application configuration or installing any service.

Ignored machine evidence: `.local/browser-session/typecheck.txt`, `build.txt`,
`build-symlink-initial.txt`, `build-dependency-copy-initial.txt`, `test-list.txt`
and `candidate-evidence.json`. The machine manifest binds the final source/report
hashes and records browser execution as pending.

## Browser cases prepared and still pending

`apps/web/tests/session-boundary.spec.ts` covers:

1. Real login/logout, removal of both tabs' private textareas/subtrees, detached
   node checks, server session rejection and preservation of unrelated storage.
   An injected queued lock notification additionally checks that a newer active
   storage marker cannot cause an older boundary event to be ignored.
2. Injected logout transport failure after real login: DOM removal, truthful
   unconfirmed UI in both languages, still-valid server session, blocked reload,
   and successful fresh-login recovery without the old draft.
3. Real HTTP session revocation followed by a browser API 401 and subtree removal.
4. A real CSRF response obtained with `route.fetch()`, with only its remaining-life
   header overridden to four seconds. A foreground static console page must
   unmount on the client timer without a new browser API request or focus change;
   the real backend session must still return 200 afterward. This is explicit
   header fault injection, **not an actual backend absolute-expiry/8-hour test**.
5. Browser offline/online events, blocked reload with the original server session,
   marker schema, and fresh-login recovery.
6. Injected persisted pagehide/pageshow events. This is handler coverage, **not**
   proof that a particular browser actually admitted/restored this page in BFCache.
7. Real authenticated logout preceded by JSON CSRF retrieval despite a deliberately
   wrong legacy-named CSRF cookie.
8. Organisation-SSO preflight with recorded provider navigation: an abandoned
   flow cannot reopen the old session, while a genuinely new development-issued
   server session on a callback-equivalent full navigation can reopen it. This
   tests the shared restoration branch; it is **not a live OIDC provider login**.

Run these only against the integrated candidate web image and matching stable-CSRF
backend, using an isolated labelled development acceptance stack. Suggested command:
`CARGOPULSE_E2E_URL=http://localhost:<isolated-port> npm run e2e -- apps/web/tests/session-boundary.spec.ts`.
The browser origin must equal the backend's configured `APP_BASE_URL`; do not
substitute `127.0.0.1` for `localhost` without updating that isolated configuration.
The suite uses real HTTP session endpoints and private unsaved form markers; it
does not reset a database or change identities/roles/policies. The lead must run
the existing Recover/browser regression suite as well and record the actual image
IDs and results. Native BFCache behavior and a real enterprise OIDC callback remain
separate acceptance work. No old running service was used as new-code E2E evidence.

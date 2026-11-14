# Evidence and claim boundaries

## Supported claims

CargoPulse has an actual locally running authenticated Recover application backed
by PostgreSQL, private persisted source files and a durable worker. It executes
HiGHS and two reference heuristics, independently verifies physical assignments and
metric provenance, records immutable human decisions and exports audited evidence.
Local container, API, browser, tenant/role, telemetry and recovery tests are recorded
in `TEST_REPORT.md` with their actual scope and outputs.

The current synthetic native benchmark contains 585 complete runs: 450 mixed
plans (five sizes, 30 seeds, three policies) plus 135 negative-control plans (five
sizes, three seeds, three profiles, three policies). Every plan passed the separate
verifier. These results are synthetic single-process measurements and are bound to
source hashes and saved inputs/configuration. They are not airline performance,
hosted latency, concurrency results, population reliability or a production SLA.

The UI's 48-hour rate describes a **proposed first flight departure**, with both
eligible-ULD and all-affected-ULD denominators shown. It is not physical arrival,
confirmed/approved protected capacity, an AWB rate or operational re-protection.
An in-app approval records a human decision; it does not reserve or dispatch cargo.
Weighted hours are policy-weighted delay for assigned cargo, not money or revenue.
Urgency is a deterministic operational cost-of-waiting replay, not statistical VaR.

## Unsupported claims

- No source-reported 87.3%, -8.5%, 0.7-second or approximately 1.1-second PDF
  headline has been reproduced or inserted as computed output.
- No airline partnership/endorsement, authorised airline data feed, airline policy
  sign-off, load-control clearance, dangerous-goods certification, physical packing
  or real temperature continuity has been established.
- No public L1 availability, real enterprise IdP acceptance, hosted CI green,
  cloud encryption/private-bucket policy, delivered on-call alert, production
  RPO/RTO or legal/privacy approval has been verified.
- No ASVS compliance, complete penetration assessment, vulnerability-free image
  or blanket security clearance is claimed. Current exact-image HIGH/CRITICAL
  gates pass; lower findings, assessment/owner work and external gates remain open.
- Protect is unavailable. No operational external write, booking, dispatch,
  notification or load request is implemented or performed.

The supplied PDFs are retained as team-reported background references. Their raw
simulator and original experiment logs were not supplied. Historical 90-run local
archives remain separate from the newer 585-run cohort; original timing figures
must retain their original version and sample-size limitations.

The current security milestone's 263 Python tests, 14 Chrome tests and actual
local image/restart/restore results have separate raw evidence. Explicit injected
browser TTL, failed transport, page events and provider navigation are not native
BFCache, full-duration expiry or enterprise IdP acceptance. The offline final
artifact review does not execute containers. The 585-plan benchmark was not rerun
on the new images, and an independent old-source review is not promoted to current
source acceptance. See the dated test and release reports for these distinctions.

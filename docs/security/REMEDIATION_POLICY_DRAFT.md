# Proposed vulnerability remediation policy

Status: **DRAFT — accountable owner acceptance and assignments pending**.
Prepared 2026-11-12 for the synthetic Recover release candidate. This document
proposes a concrete operating policy; it is not an accepted SLA or release sign-off.
No owner name, risk acceptance, past scan cadence or deadline compliance is invented.

## Proposed deadlines and release behavior

- Critical: triage within one working day; contain immediately if reachable;
  deploy a verified correction within seven calendar days of first detection.
- High: triage within two working days; correct within 30 calendar days.
- Medium: triage within seven calendar days; correct within 90 calendar days.
- Low: triage within 14 calendar days; correct within 180 calendar days.
- Unknown severity: classify within seven calendar days, then apply the assigned
  severity deadline from original detection, without resetting its clock.
- Every public release requires a fresh scan of the exact promoted image digest,
  package audits, regression evidence and review of all unresolved findings.
  HIGH/CRITICAL results block the configured image gate. A document or package
  audit cannot silently waive that executable gate or the original release gates.

The proposed owner must retain the earliest recorded detection, package/version,
image digest, advisory/vendor source, fixed-version availability, reachability
assessment, responsible engineer, due date and verified correction. Rebuilding
or renaming an image does not restart a deadline. A vendor with no available fix
requires a documented containment/change decision; it is not automatically safe.

## Proposed responsibilities and cadence

The product/release owner accepts this policy and appoints a security triage owner,
runtime dependency maintainer, database maintainer and deployment/on-call owner.
One person may hold multiple roles, but all are currently **UNASSIGNED**.
Only the accountable release owner can approve publication after all required
reviewers accept its evidence and the original red-line gates are satisfied.

Proposed automation: scans on each change/release and daily on the active published
digests; weekly manual reconciliation of lower-severity/unknown findings and vendor
fixes; monthly dependency-update review. GitHub publication, hosted scheduled runs,
alert routing and named responders have not been configured or verified locally.
The repository's change/release CI definition exists; local checks are not hosted CI.

## Current build reconciliation

`docs/evidence/security-final/lower-severity-triage.json` binds every currently
reported lower-severity package finding to the actual scanned image and raw report.
It records severity targets and unassigned review state, not exploitability,
accepted exceptions or completed remediation. Repeated CVEs across packages/images
remain separate scanner findings and are not advertised as unique vulnerabilities.

The former HIGH/CRITICAL-bearing Debian runtime was replaced with a minimal Debian
API/web closure and patched Alpine PostgreSQL. Original package metadata and image
SBOMs are retained; four image gates pass without ignore files or unfixed filters.
Remaining medium, low and unknown findings still require owner-led triage, including
whether a vendored binary is affected. Scanning is not a full security assessment.

Before this policy can be accepted, the accountable owner must name the responsible
people, accept/change the proposed timings and fund the hosted cadence/response.
Only then can due dates and policy compliance be established. ASVS V15.1.1 and
V15.2.1 therefore remain **EXTERNAL_NOT_VERIFIED**, with this draft and current
reconciliation as preparation rather than acceptance.

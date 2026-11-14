# Lead-run clean-checkout installation fallback

Baseline: `9a92fc16d297f4e65cc5a845fcbdcd1126810af5` in the separate
`.worktrees/clean-install` checkout. The requested Sol/high independent install agent
could not start because of its account usage limit. The lead executed the procedure
instead. **This does not satisfy the second-person installation sign-off.**

The clean checkout had no node_modules or virtual environment. The documented
`python3 scripts/configure_local.py` and Docker Compose build/up commands created a
NEW project `cargopulse-clean-install` with separate volumes and loopback port 3111.
No root-stack or test databases were modified. Fresh private secrets were generated
without logging them. The app used a separate non-owner PostgreSQL role.

The actual eight-ULD HTTP flow imported/committed, created a scenario, queued while
worker/Redis were stopped, survived API restart, completed after worker recovery,
independently passed validation and recorded an in-app decision. A second restart
preserved job/plan/receipt hashes and idempotent retries returned the same objects.
Six known cross-tenant scenario/job/plan/JSON/CSV/PDF requests returned 404. Auditor
read audit successfully and its solve attempt returned 403. Only the web port was
published, on 127.0.0.1. See `clean-install.json` for IDs, images and measurements.

The isolated stack was stopped at the end with volumes preserved. Generated evidence
was copied to the root and the checkout's tracked baseline evidence was restored.
No project source was modified in that checkout. Later root changes (development
session invalidation, public notices, hardened PostgreSQL and readiness) were not
part of this particular baseline; final revision review remains separately tracked.

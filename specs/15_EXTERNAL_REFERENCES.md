# 15 — External References and Research Notes (verified 2026-11-09)

## Standards and aviation context
1. **IATA ONE Record** — data exchange standard, JSON-LD/data model, API/security; https://www.iata.org/en/programs/cargo/e/one-record . IATA's July 25, 2026 endorsed release includes ontology **3.3.0** and API **2.3.0**: https://github.com/IATA-Cargo/ONE-Record/releases . The deployed partner version must be verified by integration testing, never assumed.
2. **ONE Record implementation specification** — stable 2026-07: https://iata-cargo.github.io/ONE-Record/ and https://iata-cargo.github.io/ONE-Record/2026-07/Data-Model/ . Do not invent ONE Record object fields.
3. **ONE Record demonstrator (research only)** — https://github.com/IATA-Cargo/one-record-demonstrator . It uses development credentials and is not an application security blueprint; never copy defaults to production.
4. **Cathay Cargo public API catalogue** — https://www.cathaycargo.com/en-us/help-and-support/cathaycargo-APIs.html . Publicly listed Quote, Booking, Booking Details, Cancel, Track/Trace and Push APIs; documentation does **not** grant access or an operational loading/recovery write interface.
5. **Cathay Cargo digitalisation and AI** — https://www.cathaycargo.com/en-us/about-us/digital-innovations.html . Cathay publicly describes existing digital hub, Cargo Connect and load-diagram capabilities; position CargoPulse as a complementary *decision-support* layer, not claiming Cathay lacks digital tools.
6. **IATA ULD Regulations** — https://www.iata.org/en/publications/manuals/uld-regulations/ . 2026 14th edition contains operational/contour compatibility requirements; commercial/licensed contents are not included with this handoff.
7. **IATA ULD safety** — https://www.iata.org/en/programs/cargo/cargo-operations/unit-load-devices . ULDs are subject to certification/airworthiness and handling requirements; a mass/volume MILP is not a complete load-control system.
8. **Dangerous goods** — IATA DGR 67th edition (2026) and ICAO Technical Instructions; official IATA PDF of significant changes https://www.iata.org/contentassets/90f8038b0eea42069554b2f4530f49ea/dgr-67-en-significant-changes.pdf . Obtain approved operational rule data rather than extracting limited excerpts.

## Engineering
9. **HiGHS/HiGHS Python** — https://github.com/ERGO-Code/HiGHS ; https://pypi.org/project/highspy/ ; high-performance open-source MIP solver; audit exact package licence and pin version in lockfile.
10. **Google OR-Tools CP-SAT** — https://developers.google.com/optimization/cp/cp_solver/ ; supports integer-only constraint model and explicit optimal/feasible/time-limit statuses. Consider **alternative solver** after benchmarking, not as an undisclosed drop-in.
11. **Next.js App Router and deployment** — https://nextjs.org/docs/app and https://nextjs.org/docs/app/getting-started/deploying . Deploy Node/Docker for full features, not static export.
12. **FastAPI deployment** — https://fastapi.tiangolo.com/deployment/concepts/ . Separate heavy optimisation from API worker processes; run migrations once on deploy.
13. **OWASP ASVS 5.0.0** — https://asvs.owasp.org/ ; stable security standard for application requirements.
14. **OWASP API Security Top 10** — https://owasp.org/projects/api-security-project . Object-level authorisation and unsafe API consumption particularly relevant to multi-tenant cargo data.
15. **OpenTelemetry Python** — https://opentelemetry.io/docs/languages/python/instrumentation/ . Trace across API and solver job correlation, redact sensitive baggage.
16. **Hong Kong PCPD / PDPO principles** — https://www.pcpd.org.hk/english/ ; official principles on purpose, data accuracy, retention, security and access. Partner counsel must review any real personal data/cross-border transfers.

## What these sources establish (and what they don't)
- The aviation standards and public APIs exist; **they do not certify this proposed optimiser or grant business integration access**.
- Web frameworks and solvers are production-capable technologies; using them does not prove the resulting app is production-ready without tests and operation.
- Official ONE Record test suites, SDKs or demonstrators may accelerate authorised integration, but must undergo licence, maintenance and security review. No code is assumed available from the team's hackathon.

## Before implementation
Agent must check current upstream release notes and licence terms during dependency selection; record exact versions/commit hashes in ADR and lockfiles. This planning snapshot intentionally avoids a guessed fixed runtime matrix. Legal/airline standards reviewed as of date above must be refreshed with qualified domain owners before L2.

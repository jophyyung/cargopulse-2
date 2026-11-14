# Source audit and architecture gaps

Read on 2026-11-10: README, START_HERE, Chinese instructions, all 16 specifications,
four operations documents, seven agent documents, checksum manifest and both PDFs.
All 20 slides and the one-page reference were rendered and visually inspected;
slide text extraction was empty, so extracted text alone was not used.

- Slides SHA-256: `ba01259bc592d9b2b21fc6696d54cadbf63c2c219778f4f1f910527ae2429cbc`.
- One-pager SHA-256: `bd9eead03a5f2086d30ab5ccf8e1a75930eed1eeb6ff3ae26c7e128b2985360e`.
- Both contain team-reported synthetic results. No raw simulator, solver logs or
  statistical replication source was supplied. None is inserted as app output.
- The PDF's additive priority objective does not mathematically guarantee hard
  service preservation; ADR-002 specifies explicit obligation constraints and a
  lexicographic solve. The planning package already requires that distinction.
- Re-protection in L1 means approved in-app synthetic capacity, not external booking.
- No original application, Git history, Docker, PostgreSQL or Redis binary was
  present at discovery. Tools may be provisioned in an ignored local directory;
  installed binaries and actual tests must be documented separately.
- External L1 dependencies: hosting/region, real OIDC/MFA, domain/TLS, production
  secrets/encryption, legal/privacy review and named operations/release owners.
- L2/L3 remain blocked on partner permissions, data, licensed rules and authority.

Dependency selection consulted official Next.js installation/deployment, FastAPI
release notes, SQLAlchemy docs, HiGHS Python examples, PyJWT usage, PostgreSQL row
security and package registries on 2026-11-10. Exact resolutions are in lockfiles.
The Sites Worker runtime cannot host the requested Python/Postgres/HiGHS process
architecture, so this repository uses the specified portable Node/Docker stack.

The initial package README is preserved byte-for-byte in
`docs/PLANNING_PACKAGE_README.md`; root `README.md` now documents the actual app.
The original planning checksum manifest describes the imported planning package,
not the later application or its generated evidence. Reference PDFs are unchanged.

# ADR-001: Recover platform and contract baseline

Status: accepted for synthetic L0 engineering; L1 release is not approved.

The entire planning package and both supplied PDFs were read before implementation.
The supplied files are `E275_slides copy.pdf` (20 raster pages) and
`E275_onepager copy.pdf` (one page); the names differ from the planning references.
Their SHA-256 digests are recorded in `docs/SOURCE_AUDIT.md`. No simulator source,
airline authorisation, certified aircraft envelope or production credentials exist.

Use a Next.js Node server, FastAPI modular monolith, PostgreSQL and a separately
leased HiGHS worker. Redis carries hints; PostgreSQL jobs and transactional outbox
remain canonical. An independent validator has separate logic and ownership from
the candidate builder and MILP. It recomputes physical resources and gates from
the immutable snapshot, not the solver's candidate PASS flags.

Canonical Pydantic models live in `packages/contracts/python`. The OpenAPI registry
is explicitly a contract generator, never a runtime server. Runtime response models
must match it; generated TypeScript is checked in. Decimal strings carry physical
measurements, all canonical times are UTC and airport zones are explicit IANA IDs.

The graph (cargo, pieces, AWBs, legs, position pools, handling windows, clearances)
is one immutable JSONB snapshot aggregate. This preserves explicit many-to-many
AWB/ULD identity without requiring mutable, partially updated source tables in L1.
Indexes on snapshot source/event/version prevent event duplication. Normalised
operational master-data tables are a later expand/migrate change before L2.

Position pools have explicit contours, per-unit limits, aggregate kg/m3 and slots;
they are conservative synthetic envelopes. This does not certify aircraft balance,
physical packing or DG compliance. Missing or expired verified permission excludes
an arc. Whole ULDs are atomic; splitting/rebuilding is disabled. Multi-leg paths
require explicit connections and ground resources on every leg.

Protect is architected as a future bounded module and remains disabled until its
own validator and acceptance flow pass. No Protect performance is advertised.

Alternatives: a static/Streamlit UI fails the persistent workflow requirement;
microservices add coordination cost; CP-SAT would require separate scaling proof.
Rollback: additive schema migration and prior image; never erase decision history.

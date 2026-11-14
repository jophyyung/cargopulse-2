# 09 — Data Ingestion, Authorised Integration and Data Quality

## Strategy
Build a production-quality ingestion **framework** first; do not pretend to have access to Cathay APIs. L1 works with signed/traceable synthetic JSON and CSV; L2 can replace adapters with approved airline exports or APIs without changing optimisation logic.

## Three connector modes
1. **Reference import:** operator uploads a bounded CSV or JSON file via signed browser upload. Server validates schema, units, duplicates, source identity and cross-references; raw file encrypted in private bucket. `TEAM_SYNTHETIC_UNVERIFIED` badge mandatory for generated dataset.
2. **Scheduled batch adapter:** only after partner agreement; pull from allowed endpoint or managed bucket with client credentials, allowlist, TLS verification, rate control, cursor/etag handling and backfill. Never scrape Cathay's website or reuse the competition snapshot as live feeds.
3. **ONE Record connector:** IATA ONE Record 2026-07 stable endorsed ontology 3.3.0 and API 2.3.0 are relevant references; JSON-LD/linked object model mapped into canonical AWB/ULD/flight/event records where corresponding fields exist. Do not assume ONE Record alone exposes actual load-position capacity, roster, DG clearance or airline approvals. Configure missing fields through validated other authorised feeds.

## Real Cathay capability boundary
Cathay publicly advertises Quote, Booking, Booking Details, Cancel Booking, ONE Record Track & Trace and Push APIs. This **does not prove** the team has credentials or that capacity, load-control, ground staffing and re-protection write-back are available. Keep adapter status `DISABLED_UNAUTHORISED` until an authorised sandbox contract and exact spec are provided.

## Import pipeline
`RECEIVED → MALWARE_SCANNED → PARSED → SCHEMA_VALIDATED → CROSS_REFERENCED → QUARANTINED | READY → APPROVED_IMPORT → SNAPSHOT_COMMITTED`.
- File type allowlist, content-sniffed MIME, row/size/decompression caps, file hashes and malicious formula neutralisation (CSV injection). Reject or neutralise strings beginning formula operators on re-export.
- External entity IDs and event versions required for dedup. UTC data with original local timestamp and source zone; DST ambiguity fails validation.
- Idempotent import per tenant/source/content digest; same event correction creates a new version and invalidates downstream scenarios.
- Data quality preview shows unknowns, inconsistent capacity, unrecognised ULD contour, mismatched AWB contents, expired cold-chain checks and impossible arrival/cutoff order.
- Tiered constraints: BLOCKING (safety, feasibility), REVIEW_REQUIRED (business confidence), INFORMATIONAL.
- Never fill missing safety fields with synthetic values in a live-labelled dataset.

## Required fields for first Recover adapter
`event_id`, `source_id`, `observed_at`, `event_type`, `affected_uld_ids`, `ULD→AWB associations`, `uld_type/contour`, `actual_mass_kg`, `actual_volume_m3`, `required_handling_flags`, `DG/cold-chain verification state`, `status/readiness`, `original_arrival_commitment_utc`, `service_class`, `candidate_flight IDs`, `flight leg UTC time`, `remaining capacity kg/m³/ULD position`, `closeout cutoff`, `min_transfer`, `station handling resources`, `position compatibility`, `as_of`/provenance. Missing hard-critical fields block automatic feasibility acceptance.

## Example adapter contract
```python
class IngestAdapter(Protocol):
    def describe_source(self) -> SourceDescriptor: ...
    async def fetch_since(self, cursor: str | None) -> AsyncIterator[RawRecord]: ...
    def verify(self, item: RawRecord) -> VerificationResult: ...
    def normalise(self, item: RawRecord) -> list[CanonicalEvent]: ...
```
Adapter code has no access to approval/write APIs. Outbound credentials restricted to source read scopes by deployment policy. Use replayable recorded fixtures with secrets removed for tests.

## Source freshness policy
No universal freshness claim. Configure per-feed thresholds with controller sign-off: flight status (e.g. 1 minute), capacity (e.g. 5 minutes), cold-chain validation (explicit validity window), DG clearance (event and version based). These are **initial suggested values** not Cathay-approved limits. At expiration: affected plan becomes STALE; if safety relevant, `approvable=false` and reason displayed.

## Shadow mode, timeline integrity
In historical replay, only ingest records with `observed_at ≤ simulated_decision_time`; never leak information from the future. Save feed delay distribution, missing records, manual corrections and fallbacks. Compare recommendations to real operational decisions only when partner grants access and metrics/denominators are aligned.

## Privacy and licence
No student personally identifiable information or real shipper identifiers in L1 synthetic fixtures. At L2, process only minimum required shipment and operator data under partner agreement, retention and region rules. Scope connector metadata per tenant, use contract review and respect ONE Record licence/standard version governance.

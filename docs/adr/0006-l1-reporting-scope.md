# ADR-006: Synthetic Recover reporting boundary

Status: implemented engineering scope for the synthetic Recover candidate;
public release remains subject to the unchanged release gates.

The L1 candidate emits four independently recomputed `SolutionPlan.metrics` rows:
proposed first departure within 48 hours for eligible ULDs and all affected ULDs,
assigned-cargo weighted delay hours, and explicit unassigned ULD count. Each keeps
cohort, window, source, method, statistic, units, numerator/denominator and hashes.
Solver time/status/bound/gap and validator violations are separate typed plan
telemetry, with distributions in the reproducible benchmark reports.

The broader catalog in specs/16 is not claimed as fully implemented or measured.
Actual offload AWB/ULD rates, approved protected capacity, delivered lateness and
carried billable weight require appropriate operational records/definitions that
were not supplied. Proposal assignments cannot establish those outcomes. Do not
substitute proposal departure rates or synthetic source headlines for them.

No-compliant-path count is derivable from all-affected minus eligible denominators;
per-unit exclusions and escalations are exposed. Replan churn against an approved
reference plan, a separate late-delivery metric, and additional catalog rows remain
reporting extensions with explicit definitions/provenance before implementation.
The current interface does not show fake or metadata-free values for absent KPIs.

This scope preserves the L1 metric-safety gate for what is actually displayed. It
does not waive any requirement for a later full operational analytics release or
authorised L2 pilot. It also does not demonstrate real cold-chain temperature
continuity; that needs richer approved source/rule data and domain acceptance.

The independent final numerical review at e40c676 exercised zero denominators,
frozen/service obligations, multi-leg departure/arrival semantics, objective-versus-
delay separation, pruning, lineage and future proof exclusion without finding a
new defect in these four calculations. Its bounded result is not full aviation or
mathematical certification.

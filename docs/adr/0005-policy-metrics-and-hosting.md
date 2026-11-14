# ADR-005/006/007: Mapping, policy, metrics and deployment boundaries

Status: engineering choices accepted; hosting/region/retention awaiting owner input.

Every physical piece has one AWB and one ULD in a snapshot; AWBs can span ULDs.
No ULD recovery rate is labelled as AWB performance. Proposed 48-hour assignments
are labelled proposals; approved capacity records are reported separately. Neither
is a promise of physical arrival. All metrics retain denominator, cohort, UTC window,
snapshot/policy hashes, method, source tier and reference baseline definition.

Published rules require a different author/reviewer and content hash. Published
policies cannot be edited. L1 synthetic fixtures explicitly identify a synthetic
author and reviewer, which is not an airline policy sign-off.

No hosting account, domain, OIDC tenant, cost approval, on-call owner or legal review
was supplied. Prepare production images, TLS/secret-manager runbook and staging
checks; do not publish while any L1 red line fails. Local PostgreSQL/Redis tests
are not hosted L1 acceptance. Region and backup retention remain configurable;
15-minute RPO and four-hour RTO are targets until a timed restore exercise proves them.

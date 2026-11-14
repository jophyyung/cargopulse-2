# 14 — Open Decisions and External Dependencies

## Status vocabulary
`BLOCKING_FOR_L1` = prevents public synthetic deployment; `BLOCKING_FOR_L2` = can build L1 but not authorised partner pilot; `DECIDE_WITH_TEAM` = product policy choice; `CONFIRM_WITH_AIRLINE` = only real operator/data owner may answer.

| ID | Question | Default for engineering | Owner / gate |
|---|---|---|---|
| D-01 | Has Cathay approved use of its brand and proprietary integration? | No; neutral app branding, no logo, synthetic-only | CONFIRM_WITH_AIRLINE / L2 |
| D-02 | Which operator is legal authority to accept recovery vs load-control decision? | in-app controller approval only, no external write | CONFIRM_WITH_AIRLINE / L2 |
| D-03 | Actual cabin/hold contour, DG and W&B constraints? | conservative unknown → block, no safety certification | CONFIRM_WITH_AIRLINE / L2 |
| D-04 | Valid ONE Record + Cathay API credentials and scope? | connectors disabled, signed CSV only | CONFIRM_WITH_AIRLINE / L2 |
| D-05 | AWB/ULD/piece split/rebuild handling? | full mapping, whole ULD atomic until approved split | CONFIRM_WITH_AIRLINE / L2 |
| D-06 | What is meant by “re-protected in 48h”: reserved flight, arrival or notification? | default: approved reserved capacity; UI label precise | DECIDE_WITH_TEAM before report |
| D-07 | Priorities/contractual service guarantees and penalty units? | configurable versioned policies with conservative obligations | CONFIRM_WITH_AIRLINE / L2 |
| D-08 | Do existing Cathay tools already solve overlapping use case? | assume overlap; discover workflows and differentiate | CONFIRM_WITH_AIRLINE / L2 |
| D-09 | Hosting region, tenant identity provider and retention? | configurable hosting; synthetic-only initial | DECIDE_WITH_TEAM before public L1 |
| D-10 | Is the claimed Python/HiGHS simulator source available? | no; reconstruct from specification, report mismatches | DECIDE_WITH_TEAM before external benchmark claims |
| D-11 | Should Protect be shipped together with Recover? | build Recover first, Protect P1 | DECIDE_WITH_TEAM |
| D-12 | External connector payload schema and licence? | wait for provider sample & consent, build adapter interface | CONFIRM_WITH_AIRLINE / L2 |
| D-13 | Operating-time targets? | measure against 30s job default, not 0.7s guarantee | CONFIRM_WITH_AIRLINE / L2 |
| D-14 | UI language? | English primary, Traditional Chinese supported | DECIDE_WITH_TEAM |
| D-15 | Billing/third-party SaaS multi-tenancy? | single logical tenant-ready architecture, no billing | DECIDE_WITH_TEAM; non-goal |
| D-16 | Staff response time and consent for approval? | business owner to define; no automatic notification | CONFIRM_WITH_AIRLINE / L2 |
| D-17 | Egress, storage encryption, DPA and personal-data roles? | least privilege and no real data until signed | CONFIRM_WITH_AIRLINE / L2 |
| D-18 | Authorized status of IATA DG/ULD manual data? | do not embed licensed manual; rule register referenced but pending | CONFIRM_WITH_AIRLINE / L2 |

## Questions for Cathay master-class/pilot contacts (prioritised)
1. For offloaded shipments, which decisions are currently manual, which systems record them and what changes require formal load-control approval?
2. Can a read-only feed expose ULD contents, aircraft-slot constraints, cutoffs, cold-chain verification and actual remaining capacity with trustworthy timestamps?
3. How do operators define and measure 48-hour “re-protection”, especially for no-compliant-path units and split AWBs?
4. Which offload reason codes can Protect legitimately influence and what percent of incidents are structurally uncontrollable?
5. Which service commitments are absolute constraints vs discretionary priorities and who signs off weight values?
6. Could we use 3 months of de-identified historical events and 2–3 routes for a secure shadow test? What is approval/hosting process?
7. What evidence would be required to trust a plan (source freshness, proof of capacity, explainability, conservative fallback, audit)?

## Engineering resolution rule
If answer not known: implement a safe placeholder interface or synthetic fixture, mark as open and keep live connector disabled. Never guess a policy and silently mark it compliant. Every resolved decision updates ADR, model contracts and acceptance tests.

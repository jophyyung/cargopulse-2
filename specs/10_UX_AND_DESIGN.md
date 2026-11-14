# 10 — UX Specification, Visual System and Accessibility

## Design goal
A professional air cargo operations console: **high information density without tiny corner text**, visible provenance, evident human control, analytical charts that answer a decision question, precise wording and minimal visual noise. Design must be legitimate as a commercial product, not a “pitch deck inside a browser”. Avoid generic dark-teal SaaS dashboards and gratuitous 3D hero backgrounds.

## Information architecture
1. `/login` — OIDC only, tenant name, security notices.
2. `/operations` — Recover first screen: incident queue with severity, latest input time, affected ULD, late-connection urgency, blockers, owner and action.
3. `/operations/[scenarioId]` — scenario workspace: Overview, Candidates, Plans, What-if, Audit; show `SYNTHETIC` or `AUTHORISED LIVE` label.
4. `/plans/[planId]` — decision sheet: human-readable recommendation, delta to previous plan, restricted and unassigned ULDs, hard-gate pass status, confidence/provenance, alternatives, approval.
5. `/protect` — capacity dashboard and pre-cutoff proposal, separate AWB and ULD metrics, actual mass vs volume vs slot.
6. `/evidence` — historical replay, paired baselines, distribution of results, weighted hours, denominator and cohort filters.
7. `/policies` — settings with draft/publish/revert workflow for service weights, freeze windows and capacity tolerances.
8. `/integrations` — data source status, last success, mapping, scope, schema and permission; never imply configured live Cathay connection by default.
9. `/audit` — searchable permissioned decision history, export.
10. `/help` — operational glossary, what R-VaR means/does not mean, safety scope, emergency fallback.

## Most important screen: Recovery Workspace
```
Header: CargoPulse | [Tenant] | READ-ONLY | Input as of 13:21Z | [Scenario #]
Left:  Event timeline / affected ULDs / quality issues
Middle: Feasible network plans (table + schematic route) / urgency cliff / assignment differences
Right:  WHY THIS PLAN: hard gates, last cutoffs, policy weights, alternatives, no-path reasons
Bottom: operator notes / Compare 3 policies / [Approve in-app] [Reject] [Escalate]
```
- A map is optional and must never obscure resource timelines and exact connection cutoffs. Do not display invented route distance/time.
- Show local time and UTC tooltip; user can switch display zone while immutable back-end times remain UTC.
- “Optimised” is not “authorised”. A status chip must distinguish VALIDATED PLAN, OPTIMAL, FEASIBLE TIME-LIMITED, STALE, NEEDS VERIFICATION, ESCALATED.
- Rejected arc reasons may be expanded to reveal actual rule/data evidence, not vague “AI chose better”.

## Visual hierarchy
- Body text ≥14px in desktop console where practical, primary tables ≥13px with density setting; important values ≥24px; no footer microtype masquerading as real sources.
- Wide operation tables with sortable columns, sticky header, horizontal scrolling on narrow desktops and keyboard access. Never shrink text endlessly to fit.
- Always encode danger with icon/label + colour; no colour-only semantics; accessible color contrast. Use tooltips for long reasons but not for mandatory instructions.
- Design tokens isolate theme choices. Suggested **neutral editorial baseline** (not final branding): graphite #222630, parchment #F6F2E9, muted brass #B79558, crimson #A34745 (only actual error states), sage #54796E for validated. Confirm palette before brand rollout. User's colour trials are inspiration, not proof of Cathay design-system approval.
- Reserved system colours: BLOCKED red, WARN amber, VERIFIED green/sage, UNKNOWN grey; they must remain semantically stable across selectable themes.
- Use accessible academic-style analytical charts: titles state findings, axes with units/denominators, baseline and method provenance, confidence bands only when computed, hover/crosshair and export.

## Important chart designs
- Recover urgency cliff with event-time cutoff markers, risk increase and explicit “no compliant route” state.
- Recover scenario network Gantt/timeline (arrival, cutoff, handling window) with capacity bars.
- Weighted-delay policies: side-by-side mean + distribution/P10–P90 + sample count; synthetic badge.
- Policy trade-off Pareto view: priority/service constraint vs network lateness; warn if axis units mixed.
- Protect frontiers: offload AWB fraction vs carried chargeable weight with exact current overbooking/booking cohorts; separate real and synthetic.
- Data completeness chart (by source) instead of a deceptive universal “confidence score”.
- Solver runtime plot p50/p95/p99 vs problem size and worst value; not single “<1 sec” badge.

## User journey / error states
1. User opens queue → sees event at risk and data status.
2. Click scenario → see why 3 ULDs cannot be evaluated and which required evidence is missing.
3. Click Solve only when snapshot passes ready check; job progress lives in panel and preserves navigation.
4. Receive plan; validate and compare; inspect implications for critical service class and frozen assignments.
5. Approval must ask user to confirm plan/snapshot hash, show immutable decision receipt, not auto-submit to airline.
6. If a fresher event arrives, show blocking stale banner and one-click create superseding scenario.
7. If worker fails, display reason and validated baseline/escalation; do not display stale answer as current.

## Testable design quality
- Layout screenshots and Playwright visual checks at 1280×720, 1440×900 and 1920×1080 desktop, plus tablet read-only; no clipped chart text.
- WCAG 2.2 AA as target, screen-reader table semantics, focus outlines, contrast and reduced-motion support.
- User testing: Controller can identify high-risk ULD, blocked assignment and recommended alternative within an agreed realistic time; collect measures rather than asserting UX outcome.
- Internationalization: English/Traditional Chinese, proper airport codes, numeric formatting, 12/24h preferences; no literal concatenation that breaks translations.

## No fake product signals
No fake “LIVE” animation, spurious moving aircraft, invented throughput metrics, “approved by Cathay” or dummy users. An L1 system using synthetic events remains a real authenticated deployed product but visibly says **SYNTHETIC / NOT CONNECTED**.

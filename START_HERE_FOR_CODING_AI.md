# START HERE — CargoPulse Build Agent Quick Invocation

**Task:** Implement a **real, deployable** CargoPulse enterprise web application. This package is the authoritative planning/instruction bundle; it is not the product code.

1. Read `README.md` and `中文使用說明.md`, then ALL files under `specs/` and `ops/`.
2. **Multi-agent execution:** paste `agents/00_LEAD_ORCHESTRATOR_PROMPT.md` to your principal coding agent. After it freezes schemas/OpenAPI and confirms shared Git worktrees, it may delegate to `agents/01`, `02`, `03` and independently review with `04`; follow `agents/06_COLLABORATION_PROTOCOL.md`.
3. **Single-agent execution:** paste `agents/05_SINGLE_AGENT_PROMPT.md` to one powerful coding agent; it must implement and test all parts sequentially.
4. Provide `E275_slides_6(1).pdf` and `E275_onepager(2).pdf` as attached background reference **if available**. The PDF metrics are competition evidence/context, NOT verified live production results.
5. Tell the agent to continue implementation until the L1 release criteria in `ops/02_RELEASE_GATES.md` are demonstrably satisfied, or report external blockers with exact code/tests/runbook evidence.

**Default stack:** Next.js + TypeScript, FastAPI + Python, Postgres, durable queue + Redis, highspy/HiGHS MILP, independent solution validator, OIDC, Docker, CI/CD, monitoring. **Recover first; Protect next.**

**Hard limits:** no fake dashboards; no Streamlit; no invented Cathay integration; no safety assumptions; no turning ULD rates into AWB figures; no hard-coded 87.3%/−8.5%/0.7-second results; no automatic dispatch/write-back at L1 or read-only L2; clear synthetic-data status; no claim of official Cathay endorsement without permission.

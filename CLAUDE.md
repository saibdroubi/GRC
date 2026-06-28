# Project Context: AI-Native Continuous Security Assurance & GRC Platform

This is a **commercial, multi-tenant SaaS product** to be sold to customers — not an
internal tool or a prototype. Every piece of it should be built to the standard that
implies: secure by default, professionally engineered, and held to industry best
practices. When in doubt between "fast/simple" and "secure/correct," choose
secure/correct and say so.

## Vision

Build the next generation of GRC platform, powered by AI. Do not build a traditional
GRC application — not a checklist tracker, not a spreadsheet replacement, not a manual
evidence-upload-and-dashboard tool. Build an **AI-native security assurance operating
system** where:

- Security frameworks become machine-readable knowledge, not static documents.
- Security controls become continuously measurable, not periodically assessed.
- Security tools (EDR, IAM, vuln scanners, cloud, SIEM, CMDB) are data providers feeding
  a living model of the environment, not standalone dashboards.
- Compliance is continuously computed from live state, not reconstructed at audit time.
- Evidence is automatically collected and re-validated, not manually gathered once.
- Risk is dynamically calculated from technical severity × asset criticality × business
  impact × compliance impact × threat intel — not a static severity label.
- Users interact primarily through natural language (the chat agent), with the
  dashboard as a secondary, read-oriented view.

The question the platform exists to answer, at any moment, for any customer:
**"What is our real-time security and compliance posture right now?"**

## Target architecture (north star)

```
User Interaction Layer (chat-first, dashboard secondary)
        |
AI Reasoning & Agent Layer
        |
  Compliance Agent | Risk Agent | Investigation Agent | Remediation Agent
        |
Security Knowledge Graph (Assets, Identity, Controls, Evidence, Risks, Frameworks)
        |
Security Data Integration Layer (EDR, IAM, SIEM, Scanners, Cloud, CMDB)
```

Each framework requirement should resolve to a chain: Requirement → Control Objective →
Security Capability → Evidence Requirement → Technology Source → Observed Security
State → Risk → Remediation Action. That chain is what "explainability" means here: every
AI answer should be able to walk it backwards.

## Current implementation vs. the vision (keep this section honest and current)

What exists today (see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the data model
and [backend/README.md](backend/README.md) for the service layer):

- A relational compliance model (Framework → Requirement → Control → Finding → Gap →
  Action) — this is the seed of the Knowledge Graph, not the graph itself. There's no
  asset/identity graph yet, and Control has no executable validation logic, just text.
- One general-purpose chat agent (`backend/app/chat_agent.py`) over a shared services
  layer — this is the Phase 3 starting point, not yet the specialized
  Compliance/Risk/Investigation/Remediation agent split the vision describes. Splitting
  it should happen when one agent's responsibilities/tool count actually get unwieldy,
  not preemptively.
- A pluggable integration registry (`backend/app/integrations/registry.py`) — this is
  the seed of the Security Data Integration Layer. Currently: m365, nessus (evidence
  collection working), palo_alto, burp (connection setup only, evidence TODO). No
  EDR/IAM/SIEM/CMDB integrations yet.
- A simple deterministic risk model (severity → gap severity) — not yet the
  multi-factor risk calculation (technical severity × asset criticality × business
  impact × compliance impact × threat intel) the vision describes. There is no asset
  inventory or business-criticality model yet to feed that calculation.
- A hand-written **sample** PCI DSS dataset, explicitly not the verified official
  standard — real framework ingestion (PDF → Claude extraction → admin-approved draft)
  is designed but not yet built.
- No knowledge base / long-term memory layer yet (designed, not built).
- Real authentication and RBAC are now in place: session-cookie auth with self-service
  signup/login/logout (`app/auth.py`, `app/api/auth.py`), tenant/org always derived
  from the authenticated session (never a client-supplied param), and a shared
  `app/permissions.py::require_role` gate enforced identically by REST routers and the
  chat agent. Still deferred: OIDC/SSO for enterprise buyers, email verification,
  password reset, multi-org-per-user, a user-management/invite UI — these remain
  follow-ups, not silently dropped.
- A pytest suite (`backend/tests/`) now covers auth, RBAC, tenant isolation, the gap
  state machine, and the action approval lifecycle — the security-critical paths
  exercised by hand during the auth/RBAC pass. Still not covered: anything requiring
  Claude API mocking (framework ingestion, evidence AI analysis, the chat agent's real
  tool-calling loop, knowledge-base embeddings), integration vendor adapters, and CI
  wiring (no `.github/workflows` yet) — these are gaps, not decisions.

Treat the vision document's phases as the roadmap, but don't jump straight to Phase 4
concepts (multi-agent split, autonomous remediation everywhere) before Phase 1-2
foundations (asset/identity graph, multi-factor risk model, real framework data) are
actually in place under them. Build the foundation a layer at a time; each layer should
make the next one easier, not block on it.

## Engineering & Security Standards (non-negotiable)

This is sold to multiple customers, so multi-tenant data isolation and security
posture are product features, not implementation details.

- **Tenant isolation**: every query, every service function, every chat tool is scoped
  by `organization_id`. Never trust a client-supplied org/user ID without checking it
  belongs together — and as real auth lands, derive both from the authenticated session,
  never from request parameters the caller controls.
- **No secrets in code, ever.** Integration credentials are encrypted at rest
  (`app/crypto.py`, Fernet, `SECRET_ENCRYPTION_KEY`) — keep that pattern for anything
  new that holds a credential. Master keys live in `.env`/secret managers, never in git.
- **Auth**: session-cookie based (`httpOnly`, `Secure`, `SameSite=Strict`), org/user are
  always derived from the authenticated session server-side, never from a client-supplied
  parameter. RBAC (`viewer`/`analyst`/`admin`/`owner`) is enforced at the API layer via
  `app/permissions.py::require_role`, called identically from REST routers and the chat
  agent's `_dispatch`. OIDC/SSO for enterprise buyers is still a deferred follow-up, not
  yet built.
- **Audit everything that mutates state.** `AuditLog` already covers action
  approve/reject; extend that discipline to every new mutation (config changes,
  evidence submission, framework approval, integration setup) as those land.
- **OWASP Top 10 is a baseline, checked on every change, not an occasional audit.**
  Concretely for this stack: parameterized queries only, never raw SQL string
  interpolation (A03 injection); every router/chat tool re-derives org/user from the
  session rather than trusting a client-supplied ID (A01 broken access control,
  ties back to the tenant-isolation rule above); no hand-rolled crypto, no secrets in
  code (A02 cryptographic failures, A05 misconfiguration); validate and size-limit
  every external input — uploaded documents, integration API responses, chat tool
  arguments — before it crosses into application logic (A03/A04); dependencies kept
  current and free of known CVEs (A06); auth/session handling stays in `app/auth.py`'s
  reviewed pattern rather than ad hoc per-feature reinvention (A07); treat any new
  deserialization, file upload, or webhook receiver as A08/A10-relevant and validate
  accordingly. When a change touches auth, input parsing, file/URL handling, or
  cross-tenant data access, call out which OWASP category applies in the same way the
  IDOR fixes were called out during the auth/RBAC pass.
- **AI actions respect the same RBAC and approval gates as a human would** — the chat
  agent's approve/reject guardrails (session-bound user identity, never an
  LLM-supplied parameter) are the model to follow for every new agentic capability:
  enforce the hard boundary in code, not just in the system prompt.
- **Explainability is mandatory.** Every AI-generated finding, score, or recommendation
  must be traceable to the evidence and reasoning that produced it (see `ai_rationale`
  on `Finding`, `parameters.rationale` on `Action`) — never surface an AI conclusion
  without its basis. Never let a heuristic fallback present itself as AI-verified.
- **Tests guard the security-critical paths — keep extending them, don't let them rot.**
  `backend/tests/` covers auth, RBAC (REST and chat, via `chat_agent._dispatch`), tenant
  isolation (the three IDOR classes fixed during the auth pass), the gap state machine,
  and the action approval lifecycle — confirmed to actually catch regressions (a
  reverted IDOR fix was spot-checked to fail the corresponding test). Run
  `backend/.venv/bin/pytest` against a real Postgres `grc_test` database (pgvector
  columns rule out SQLite) before considering an auth/RBAC/tenant-isolation/state-machine
  change done. As new agentic capabilities, integrations, or state machines land, add
  tests in the same pass, not as a follow-up.
- **Dependencies and input validation**: validate everything crossing a trust boundary
  (uploaded documents, integration API responses, chat tool inputs); keep dependencies
  current; don't disable security checks to move faster.

## Development principles

- **AI-first**: for every new feature, ask "can this be done through natural language?"
  and make sure the chat agent's tool surface covers it — the dashboard should never
  have a capability the chat agent lacks.
- **API-first**: every capability is a service-layer function with a thin router on
  top, callable identically by REST and by chat tools (already the established pattern
  — keep extending it, don't special-case the chat agent's data access).
- **Data-first**: AI quality is bounded by data quality — prioritize accurate
  inventory, relationships, and provenance over adding more AI surface area on top of
  thin data.
- **Explainability over confidence**: a correct "we don't know yet, here's why" beats a
  fabricated answer, always.

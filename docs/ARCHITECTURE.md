# Continuous GRC Automation Platform — Architecture & Data Model

## 1. Goal

A platform (on-prem or cloud) that continuously evaluates compliance posture (PCI DSS, HIPAA, ISO 27001, SOC 2, etc.) by:

1. Ingesting the current version of each compliance framework's requirements.
2. Continuously collecting evidence from existing systems (AD, EDR, M365, vulnerability scanners, cloud providers, ticketing, etc.).
3. Using an AI engine to analyze evidence and map it to requirements.
4. Producing live scoring, gap lists, and action items with owners.
5. Optionally acting on gaps (agentic mode) via the same integrations, gated by admin approval.
6. Exposing all of the above through a chat interface in addition to a dashboard/API.

Stack: **Python/FastAPI** backend, **PostgreSQL** (+ pgvector) datastore, **React** frontend, **Anthropic Claude** as the LLM/agent layer via the Claude Agent SDK / Tool Use.

---

## 2. High-Level Components

```
                         ┌─────────────────────────┐
                         │        React UI         │
                         │  Dashboard | Chat | Admin│
                         └────────────┬─────────────┘
                                      │ REST/WebSocket
                         ┌────────────▼─────────────┐
                         │        API Gateway        │
                         │   (FastAPI, AuthN/AuthZ)  │
                         └────────────┬─────────────┘
        ┌───────────────┬─────────────┼─────────────┬───────────────┐
        ▼               ▼             ▼             ▼               ▼
 ┌─────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────────┐ ┌───────────┐
 │ Framework   │ │ Evidence    │ │ AI Engine│ │ Scoring &    │ │ Action /  │
 │ Library Svc │ │ Collector   │ │ (Claude) │ │ Gap Engine   │ │ Remediation│
 │             │ │ Service     │ │          │ │              │ │ Engine    │
 └─────────────┘ └──────┬──────┘ └────┬─────┘ └──────┬───────┘ └─────┬─────┘
                        │             │              │               │
                        ▼             ▼              ▼               ▼
                 ┌──────────────────────────────────────────────────────┐
                 │            Integration Adapter Layer                  │
                 │  AD | EDR | M365/Graph | Vuln Scanner | Cloud | ITSM  │
                 └──────────────────────────────────────────────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │  PostgreSQL (+ pgvector)  │
                         │  Evidence blob store (S3/ │
                         │  on-prem object storage)  │
                         └───────────────────────────┘
```

### 2.1 Framework Library Service
- Stores normalized, versioned representations of compliance frameworks (PCI DSS 4.0.1, HIPAA Security Rule, ISO 27001:2022, etc.) as structured **Requirements** broken into testable **Controls**.
- Ingestion pipeline: admin uploads the official framework doc (PDF/XML) or syncs from a curated source → Claude extracts structured requirement objects → human review/approval → versioned and stored. Old versions retained for history/diffing.

### 2.2 Evidence Collector Service
- Adapter-based pollers/webhooks pull evidence on a schedule or in near-real-time from each integration (see §5).
- Normalizes raw system data (configs, logs, screenshots, exports, API responses) into an **Evidence** record with metadata (source, collected_at, control hints, checksum).
- Raw evidence stored in object storage; structured/extracted facts stored in Postgres.

### 2.3 AI Engine (core)
Built on Claude (Agent SDK), with distinct sub-tasks exposed as internal "skills":
1. **Framework parsing** — turn raw framework text into structured Requirement/Control records.
2. **Evidence analysis** — extract facts/claims from raw evidence (e.g. "MFA enforced for all admin accounts" from an AD export).
3. **Requirement matching/correlation** — embedding-based retrieval (pgvector) + LLM judgment to map evidence facts to specific controls, with a confidence score and rationale.
4. **Gap reasoning** — for unmet/partially-met controls, generate a human-readable gap description and suggested remediation steps.
5. **Chat agent** — conversational interface with tool access to query the platform's own data (read-only by default) and, in agentic mode, to invoke remediation actions through the Action Engine.

All AI steps log their reasoning/evidence trail (Findings) for auditability — every score must be traceable to evidence + the AI rationale that produced it.

### 2.4 Scoring & Gap Engine
- Deterministic layer (not the LLM) that aggregates per-control evidence status (Met / Partially Met / Not Met / Not Applicable / Compensating Control) into:
  - Per-control score and confidence.
  - Per-framework/domain rollup score.
  - Gap list with severity, owner, due date, linked evidence and AI rationale.
- Recomputed continuously as new evidence/findings arrive (event-driven), not just on a schedule.

### 2.5 Action / Remediation Engine
- Defines **Actions** (e.g. "enable MFA for user X in AD", "isolate host via EDR", "create Jira ticket for patch Y") as typed, idempotent operations against an integration adapter.
- **Agentic mode**: AI engine proposes an Action tied to a specific Gap → goes into `pending_approval` → admin approves/rejects via UI or chat → on approval, Action Engine executes via the adapter and records the result back as new Evidence (closing the loop).
- All actions are logged immutably (who/what/when/why) for audit.

### 2.6 Integration Adapter Layer
- Common `Adapter` interface (`collect_evidence()`, `list_capabilities()`, `execute_action()`) implemented per system: Active Directory/Entra ID, EDR (CrowdStrike/Defender/etc.), Microsoft 365/Graph, vulnerability scanners (Tenable/Qualys/etc.), cloud providers (AWS/Azure/GCP config), ITSM (Jira/ServiceNow).
- Supports on-prem (agent/connector deployed in customer network, outbound-only connection) and cloud (direct API/OAuth) deployment modes behind the same interface.

---

## 3. Core Data Model

```
Organization
  id, name, deployment_mode(on_prem|cloud), created_at

Framework
  id, name (e.g. "PCI DSS"), version (e.g. "4.0.1"), published_at,
  source_doc_ref, status(draft|approved|superseded)

Requirement
  id, framework_id, ref_code (e.g. "3.2.1"), title, description,
  parent_requirement_id (nullable, for hierarchy)

Control
  id, requirement_id, description, testing_procedure,
  applicability_tags[] (e.g. industry, environment scope)

IntegrationConnection
  id, organization_id, adapter_type (ad|edr|m365|vuln_scanner|cloud|itsm),
  config (encrypted), status(active|error|disabled), last_sync_at

Evidence
  id, organization_id, connection_id, control_hints[], raw_ref (object storage key),
  collected_at, evidence_type(config|log|screenshot|api_response|document),
  checksum, extracted_facts (jsonb)

Finding
  id, control_id, evidence_id, status(met|partial|not_met|not_applicable),
  confidence (0-1), ai_rationale, created_at, superseded_by (nullable)

ControlScore  (materialized/rolled-up, recomputed on Finding changes)
  id, control_id, organization_id, status, confidence, last_evaluated_at

Gap
  id, control_id, organization_id, severity(critical|high|medium|low),
  description, recommended_action, owner_user_id, due_date,
  status(open|in_progress|remediated|risk_accepted), linked_finding_ids[]

Action
  id, gap_id, adapter_type, action_type, parameters (jsonb),
  status(proposed|pending_approval|approved|executing|completed|failed|rejected),
  proposed_by(ai|user), approved_by_user_id, executed_at, result (jsonb)

AuditLog
  id, organization_id, actor(user|ai_agent), action, target_type, target_id,
  payload (jsonb), created_at

User
  id, organization_id, name, email, role(admin|analyst|owner|viewer)

ChatSession / ChatMessage
  session: id, user_id, organization_id, created_at
  message: id, session_id, role(user|assistant|tool), content, tool_calls (jsonb), created_at
```

Relationships: `Framework 1—N Requirement 1—N Control 1—N Finding N—1 Evidence`; `Control 1—N ControlScore (per org)`; `Control 1—N Gap (per org)`; `Gap 1—N Action`.

---

## 4. AI Engine Pipeline (continuous loop)

```
[Schedule/Webhook] → Evidence Collector → Evidence (raw + extracted_facts)
        → AI: extract facts → embed → match against Control embeddings (pgvector)
        → AI: produce Finding (status, confidence, rationale)
        → Scoring Engine: recompute ControlScore + Gap (create/update/close)
        → If Gap.status=open and remediation possible:
              AI proposes Action → admin approval (UI/chat) → Action Engine executes
              → result recorded as new Evidence → loop closes
```

This is event-driven (new evidence triggers re-scoring of affected controls only), with a periodic full re-evaluation sweep as a safety net.

---

## 5. Initial Integration Targets (priority order)

1. Microsoft 365 / Entra ID (Graph API) — identity, MFA, conditional access, mail security.
2. Active Directory (on-prem, via LDAP/connector) — account policy, privileged groups.
3. Vulnerability scanner (Tenable or Qualys API) — patch/vuln evidence.
4. EDR (CrowdStrike or Microsoft Defender API) — endpoint posture, isolation actions.
5. ITSM (Jira/ServiceNow) — gap-to-ticket sync, action audit trail.

Each adapter ships independently behind the common interface so frameworks/scoring work without waiting on all integrations.

---

## 6. Chat Interface

- Backed by Claude with tool-use against read APIs (frameworks, scores, gaps, evidence) by default.
- Agentic mode unlocks write-tools (`propose_action`) but execution always requires a separate approval step recorded in `Action`/`AuditLog` — the chat agent cannot self-approve.
- Same chat surface usable for: "What's our PCI score?", "Show gaps owned by me", "Draft a remediation ticket for gap #123", "Enable MFA for jane@corp.com" (→ proposes Action, asks for approval).

---

## 7. Deployment Modes

- **Cloud (SaaS)**: full stack hosted centrally; integrations connect via OAuth/API keys directly from the customer's tenant.
- **On-prem**: lightweight connector/agent deployed in customer network for adapters needing internal access (AD, internal scanners); makes outbound-only calls to the core platform (cloud) or runs the full stack locally for air-gapped customers. Same adapter interface, different transport.

---

## 8. Suggested Build Order (MVP → full vision)

1. Data model + Postgres schema, Framework Library with one framework (PCI DSS) hand-loaded.
2. Evidence model + manual evidence upload (no live integration yet) to validate scoring/gap pipeline end-to-end.
3. AI matching pipeline (embeddings + Claude) wired to real PCI controls.
4. Dashboard UI: framework score, control list, gap list.
5. First live integration (M365/Graph) replacing manual upload for a subset of controls.
6. Chat interface (read-only tools first).
7. Action Engine + approval workflow + first write-capable adapter action.
8. Additional frameworks (HIPAA, ISO 27001) and integrations.

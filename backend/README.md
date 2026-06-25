# Backend

FastAPI service implementing the Framework Library, Evidence Collector,
Scoring & Gap engine, a Claude-backed evidence analyzer, a generalized
integration framework, and a chat agent that can do anything the REST
API/dashboard can — per [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Fill in ANTHROPIC_API_KEY (enables the chat agent + AI-generated remediation
# proposals/evidence analysis) and SECRET_ENCRYPTION_KEY (required — encrypts
# integration credentials at rest; generate with the command in .env.example).

# requires Postgres with the pgvector extension available
createdb grc_dev
psql -d grc_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"

.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed   # loads a dev org + sample PCI DSS-style controls
.venv/bin/uvicorn app.main:app --reload
```

## Architecture

- `app/services/*` — the business logic (frameworks, gaps, actions,
  integrations). Both the REST routers (`app/api/*`) and the chat agent
  (`app/chat_agent.py`) call these same functions, so chat and the dashboard
  can never drift out of sync.
- `app/integrations/registry.py` — pluggable integration vendors. Each vendor
  module (`m365.py`, `nessus.py`, `palo_alto.py`, `burp.py`) registers a
  config schema, a `test_connection`, and (where implemented) a
  `collect_evidence`. Adding a new vendor means writing one module like
  those, nothing else changes.
- `app/crypto.py` — integration credentials are encrypted at rest
  (`IntegrationConnection.config_ciphertext`) with a master key
  (`SECRET_ENCRYPTION_KEY`), not stored in `.env` — this is what lets the
  chat agent actually configure an integration instead of just telling you
  which env var to hand-edit.
- `app/chat_agent.py` — Claude tool-use loop over the service layer. Two
  things are enforced in code, not just prompting: approve/reject actions
  always use the chat session's own `user_id` (the model can't pick a
  different approver), and every tool is scoped to the session's
  `organization_id` (the model can't query/act on another org).

## Key endpoints

- `GET /frameworks`, `GET /frameworks/{id}/controls-with-status?organization_id=`,
  `GET /frameworks/{id}/score?organization_id=`
- `POST /evidence`, `GET /evidence?organization_id=`
- `GET /gaps?organization_id=`, `PATCH /gaps/{id}?new_status=`
- `POST /gaps/{id}/actions`, `POST /actions/{id}/approve?user_id=`,
  `POST /actions/{id}/reject?user_id=`
- `GET /integrations?organization_id=` — status of every registered vendor
- `POST /integrations/{type}/config?organization_id=` (body: partial config
  fields), `POST /integrations/{type}/test?organization_id=`,
  `POST /integrations/{type}/sync?organization_id=&control_id=`
- `POST /chat/sessions`, `GET /chat/sessions?organization_id=`,
  `GET /chat/sessions/{id}/messages`, `POST /chat/sessions/{id}/messages`

## Integrations

Currently registered: **m365** (read-only, evidence collection implemented —
Conditional Access/MFA), **nessus** (read-only, evidence collection
implemented — latest scan severity counts), **palo_alto** and **burp**
(connection setup/testing implemented; evidence collection intentionally
TODO — see the docstring in each module).

Configure any of them either via chat ("let's integrate our Nessus scanner")
or directly:

```bash
curl -X POST "http://localhost:8000/integrations/nessus/config?organization_id=<id>" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://cloud.tenable.com", "access_key": "...", "secret_key": "..."}'
curl -X POST "http://localhost:8000/integrations/nessus/test?organization_id=<id>"
```

Each vendor module's `permissions_help` (returned by `GET /integrations`)
states exactly what credential/permission to generate on the vendor side.

## Notes

- The seeded PCI DSS data in `app/seed.py` is a hand-written sample for
  development only — it has not been verified against the official current
  PCI DSS text and must be replaced via the real Framework Library ingestion
  pipeline (designed, not yet built — see the project plan) before being
  used for actual compliance scoring.
- The knowledge base and real PCI DSS document ingestion are designed but
  not yet implemented; this pass covers the services-layer refactor, the
  chat agent, and the generalized integration framework.

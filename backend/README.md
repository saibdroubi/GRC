# Backend

FastAPI service implementing the Framework Library, Evidence Collector,
Scoring & Gap engine, and a Claude-backed evidence analyzer, per
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY, adjust DATABASE_URL

# requires Postgres with the pgvector extension available
createdb grc_dev
psql -d grc_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"

.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed   # loads a dev org + sample PCI DSS-style controls
.venv/bin/uvicorn app.main:app --reload
```

## Endpoints

- `GET /frameworks` / `GET /frameworks/{id}/requirements` / `GET /frameworks/{id}/controls`
- `GET /frameworks/{id}/score?organization_id=...` — rolled-up framework score
- `POST /evidence` — submit evidence; if `extracted_facts.status` is set it's
  trusted, otherwise Claude evaluates the evidence against each control in
  `control_hints` and a Finding/ControlScore/Gap are created or updated.
- `GET /evidence?organization_id=...`
- `GET /gaps?organization_id=...&status=open`
- `PATCH /gaps/{id}?new_status=...`
- `POST /gaps/{id}/actions` — AI proposes a remediation action (`pending_approval`)
- `POST /actions/{id}/approve?user_id=...` / `POST /actions/{id}/reject?user_id=...`
- `GET /integrations/m365/status?organization_id=...`
- `POST /integrations/m365/sync?organization_id=...&control_id=...` — pulls live
  Conditional Access policies from Microsoft Graph and records MFA-enforcement
  evidence against the given control

## Microsoft 365 / Entra ID integration

Read-only for now (no write/remediation calls). Requires an existing Entra ID
app registration with the **application** permission `Policy.Read.All`,
admin-consented in your tenant:

1. Azure portal → Entra ID → App registrations → your app → API permissions
   → Add a permission → Microsoft Graph → Application permissions →
   `Policy.Read.All` → Grant admin consent.
2. Certificates & secrets → create a client secret.
3. Fill `M365_TENANT_ID`, `M365_CLIENT_ID`, `M365_CLIENT_SECRET` in `.env`
   (directory/tenant ID, application/client ID, and the secret value).
4. Restart the backend. The dashboard's Integrations panel will show
   "configured" and the MFA control will get a "Sync from M365" button that
   pulls live Conditional Access policies and judges org-wide MFA enforcement.

## Notes

- The seeded PCI DSS data in `app/seed.py` is a hand-written sample for
  development only — it has not been verified against the official current
  PCI DSS text and must be replaced via the real Framework Library ingestion
  pipeline before being used for actual compliance scoring.

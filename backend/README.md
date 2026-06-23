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

## Notes

- The seeded PCI DSS data in `app/seed.py` is a hand-written sample for
  development only — it has not been verified against the official current
  PCI DSS text and must be replaced via the real Framework Library ingestion
  pipeline before being used for actual compliance scoring.

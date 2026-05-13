# Quoter Motor

A self-hosted web tool for recreating Flex Rental Solutions quotes with current inventory and AI-matched equivalents.

## What it does

1. You enter an existing Flex quote number
2. The tool fetches all line items from Flex
3. AI (OpenAI gpt-4o-mini) matches each item to the closest equivalent in current inventory
4. You review the matches — green/yellow/orange/red confidence indicators, approve or override each row
5. Set the new quote name/dates/client, push → a new Flex document is created

## Project structure

```
quoter-motor/
├── backend/                   FastAPI Python app
│   ├── app/
│   │   ├── config.py          Settings from .env (pydantic-settings)
│   │   ├── main.py            FastAPI app + CORS + router registration
│   │   ├── flex/
│   │   │   ├── client.py      Flex API client — auth, paginated fetches, CRUD
│   │   │   └── models.py      Pydantic models for Flex API shapes
│   │   ├── matching/
│   │   │   └── engine.py      Fuzzy pre-filter + OpenAI ranking, confidence scores
│   │   └── routes/
│   │       ├── quotes.py      /api/quotes/* — fetch, match, create
│   │       ├── inventory.py   /api/inventory/* — list + search (cached)
│   │       └── debug.py       /api/debug/* — health check, flex-connection test, raw API explorer
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                  React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── api/client.ts      Axios API client + all TypeScript types
│   │   ├── store/quoteStore.ts React context + reducer (no external state lib)
│   │   ├── components/
│   │   │   ├── ConfidenceBadge.tsx   Color-coded confidence pill
│   │   │   ├── ItemMatchRow.tsx      Per-item review row with approve/override/alts
│   │   │   ├── InventorySearch.tsx   Debounced live search for manual override
│   │   │   └── StepNav.tsx           4-step progress indicator
│   │   └── pages/
│   │       ├── Home.tsx        Step 1 — search and load a source quote
│   │       ├── Review.tsx      Step 2 — review AI matches
│   │       ├── Details.tsx     Step 3 — set new quote name/dates/client
│   │       └── Success.tsx     Step 4 — created confirmation + Open in Flex link
│   ├── nginx.conf             Served by nginx; proxies /api/ to backend container
│   └── Dockerfile
├── nginx/nginx.conf           Unused in Docker (frontend has its own); kept for reference
├── docker-compose.yml         Frontend on :3000, backend internal only
├── .env.example               All required env vars with descriptions
└── CLAUDE.md                  This file
```

## Flex API

- **Instance**: https://clearlamp.flexrentalsolutions.com/f5
- **Swagger UI**: https://clearlamp.flexrentalsolutions.com/f5/swagger-ui/index.html (OAS3, authenticated)
- **Raw spec**: `GET /f5/v3/api-docs` with `X-Auth-Token` header
- Auth: `X-Auth-Token: <api_key>` — key stored in `.env` as `FLEX_API_KEY`

See `AGENTS.md` for the full list of verified endpoints, critical API discoveries, and known issues.

## Running locally

```bash
cp .env.example .env
# Fill in FLEX_BASE_URL and FLEX_API_KEY
docker compose up --build
# Open http://localhost:3000
# Backend hot-reloads on file changes (volume-mounted)
```

## Deploying to Proxmox

```bash
git clone git@github.com:chaserbot/quoter-motor.git
cd quoter-motor
cp .env.example .env   # fill in credentials
docker compose up -d --build
# Access at http://VM_IP:3000
```

## Required credentials (.env)

| Variable | Description |
|---|---|
| `FLEX_BASE_URL` | `https://clearlamp.flexrentalsolutions.com/f5` |
| `FLEX_API_KEY` | From Flex → Integrations → API |
| `OPENAI_API_KEY` | Not currently used; kept for future AI matching phase |

## Status

**Core flow fully working as of 2026-05-13.**

Working:
- Quote search → match → review → create new Flex quote
- 40/44 items resolve by direct ID lookup on a typical quote
- Mixed gear (INVENTORY_MODEL) and labor (SERVICE_OFFERING) line items both add correctly

Known issues / next steps (see `AGENTS.md` for details):
- New quotes are flat (no subtotal grouping from source quote)
- Pricing model and defaultTime not copied from source → rates may differ
- Items with no resourceId (manually typed originals) require manual replacement

## Future phases

- **Phase 2**: Ingest RFP/RFQ, competitor quotes, email threads → AI extracts equipment list → same review/push flow
- **Phase 3**: Client-facing output mode
- **Phase 4**: Self-hosted AI model

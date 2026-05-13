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
- **API base**: https://clearlamp.flexrentalsolutions.com/f5/api/v2
- **Swagger UI**: https://clearlamp.flexrentalsolutions.com/f5/swagger-ui/index.html
- Auth: `POST /authenticate` with `{username, password}` → token (trying fields: `id`, `token`, `accessToken`)
- Auth header: `X-Auth-Token: <token>` (assumed — verify on first run)
- Filter syntax: `filter=fieldName::==value`

**The Flex API shape has not been verified against real responses yet.** Use `/api/debug/flex-connection` and `/api/debug/flex-raw?path=/element?limit=2` to explore the actual API after credentials are set.

## Running locally

```bash
cp .env.example .env
# Fill in FLEX_USERNAME, FLEX_PASSWORD, OPENAI_API_KEY
docker compose up --build
# Open http://localhost:3000
# Verify Flex connectivity: http://localhost:3000/api/debug/flex-connection
```

## Deploying to Proxmox

```bash
# On your Proxmox VM (Docker installed)
git clone git@github.com:YOUR_USERNAME/quoter-motor.git
cd quoter-motor
cp .env.example .env
# Fill in credentials
docker compose up -d --build
# Access at http://VM_IP:3000
```

## Required credentials (.env)

| Variable | Description |
|---|---|
| `FLEX_USERNAME` | Flex login email |
| `FLEX_PASSWORD` | Flex login password |
| `OPENAI_API_KEY` | From platform.openai.com/api-keys (separate from ChatGPT Plus) |
| `FLEX_BASE_URL` | Pre-filled in .env.example — don't change |

## Status

**Phase 1 complete — not yet tested against real Flex API.**

Pending:
- Fill in `.env` credentials and run `docker compose up --build`
- Hit `/api/debug/flex-connection` to verify Flex auth works
- Fix any field name mismatches revealed by real API responses
- Push to GitHub (create repo at github.com, then `git remote add origin ... && git push -u origin main`)

## Future phases

- **Phase 2**: Ingest RFP/RFQ, competitor quotes, email threads, meeting notes → AI extracts equipment list → same review/push flow
- **Phase 3**: Client-facing output mode
- **Phase 4**: Self-hosted AI model (when hardware supports it)

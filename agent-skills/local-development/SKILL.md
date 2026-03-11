---
name: local-development
description: Instructions for running and developing the Debate Analyzer app locally. Use when the user asks how to run the webapp locally, start the API or frontend, or perform local development setup.
---

# Local Development

## Running the webapp locally

### Before starting

When helping the user run the webapp locally, **ask**: "Do you want to run the webapp with an entirely new database (fresh, no data) or use the current database (existing data)?" Then follow the corresponding option below.

### Environment (repo root)

Set these in the repo root (e.g. `export` in the shell or in a `.env` file before running):

- `ADMIN_USERNAME=admin`
- `ADMIN_PASSWORD=admin`

**Database choice:**

- **Use current database** — Use existing data (default `debate_analyzer.db` or whatever they already use). Do **not** set `DATABASE_URL` (so default `sqlite:///./debate_analyzer.db` is used), or keep their existing `DATABASE_URL` if they have one. No file deletion or extra steps.

- **Use entirely new database** — Point at a different SQLite file so existing data is not used. Set `DATABASE_URL=sqlite:///./db_devel.db` (or another filename). For a **clean** DB, remove that file before starting (e.g. `rm -f db_devel.db` in repo root); the next run creates an empty DB and the app creates tables. Ensure the chosen DB file (e.g. `db_devel.db`) is in `.gitignore`.

Example – current DB (from repo root):

```bash
export ADMIN_USERNAME=admin ADMIN_PASSWORD=admin
```

Example – new DB (from repo root):

```bash
export ADMIN_USERNAME=admin ADMIN_PASSWORD=admin DATABASE_URL=sqlite:///./db_devel.db
# Optional clean start: rm -f db_devel.db
```

### Prerequisites

- Backend: `poetry install --extras webapp` (or `poetry install --extras transcribe --extras webapp`).
- Frontend: from repo root, `cd frontend && npm install`.

### Development

1. **Terminal 1 – API:** From repo root: `poetry run python -m debate_analyzer.api` → http://127.0.0.1:8000.
2. **Terminal 2 – Frontend:** From repo root: `cd frontend && npm run dev` → open http://localhost:5173 (Vite proxies `/api`, `/docs`, `/openapi.json` to the API). Hot reload for frontend.

Or use from repo root: **`make webapp-api`** (terminal 1) and **`make webapp-frontend`** (terminal 2).

### Backup option - do not use unless asked explicitly

Build the frontend and serve it from FastAPI:

```bash
cd frontend && npm run build && cd ..
cp -r frontend/dist/* src/debate_analyzer/api/static/
poetry run python -m debate_analyzer.api
```

Open http://127.0.0.1:8000. No separate Vite server.

### Shutting down the webapp

From repo root run **`make webapp-stop`**. It stops processes on ports 8000 (API) and 5173 (frontend).

### URLs

- `/` — speaker list
- `/speakers/<id>` — speaker detail
- `/admin` — register transcripts, annotate
- `/docs` — API docs

For more on env vars, database, and deployment, see [doc/WEBAPP.md](../../doc/WEBAPP.md) and [doc/HOWTO.md](../../doc/HOWTO.md).

# Web App (Speaker Profiles and Statistics)

The Debate Analyzer web app provides a database of **speaker profiles**, **transcript registration** (from S3 or local paths), and **speaker annotation** (mapping transcript speaker IDs to profiles). Public pages show speaker list and per-speaker statistics.

---

## What It Does

- **Speaker profiles:** Create and manage speaker entities (first name, surname, slug, optional bio and short description).
- **Transcript registration:** Register transcripts by S3 URI (e.g. `s3://bucket/jobs/job-id/transcripts/file.json`) or local file path (e.g. `file:///path/to/transcription.json`). The app loads the JSON and stores segments and metadata.
- **Speaker annotation:** In the admin UI, open a transcript and assign transcript speaker IDs (e.g. `SPEAKER_00`, `SPEAKER_01`) to existing speaker profiles. This links transcript segments to profiles for statistics.
- **Public stats:** Public API and pages list speakers and show per-speaker statistics (e.g. number of transcripts, total segments, speaking time) derived from registered transcripts and annotations.

---

## Run Locally

### Install

**Backend (Python):** Install the web app extra (or both transcribe and webapp for full local dev):

```bash
poetry install --extras webapp
# or
poetry install --extras transcribe --extras webapp
```

**Frontend (Vue):** The UI is a Vue 3 SPA in `frontend/`. From the repository root:

```bash
cd frontend && npm install && cd ..
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection URL. | SQLite file `debate_analyzer.db` in the current working directory. |
| `FORCE_SQLITE` | Set to `1` or `true` to use SQLite even when `DATABASE_URL` is set (e.g. local dev with RDS URL in env). | — |
| `ADMIN_USERNAME` | HTTP Basic auth username for `/admin` and `/api/admin/*`. | If unset, admin routes may be disabled or accept any credentials depending on implementation. |
| `ADMIN_PASSWORD` | HTTP Basic auth password for admin. | — |

For local development, SQLite is sufficient. If your environment has `DATABASE_URL` pointing at AWS RDS (e.g. from a shared `.env`), either unset it (`unset DATABASE_URL`) or set `FORCE_SQLITE=1` so the app uses the local SQLite file. For production (e.g. on AWS), use PostgreSQL and set `DATABASE_URL` (the ECS task definition injects it).

**Example (optional admin auth):**

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin
```

### Start the Server

**Option A – Development (recommended):** Run the Vue dev server and the API separately. The dev server proxies `/api` and `/docs` to FastAPI.

1. Start the API (from repository root):

   ```bash
   poetry run python -m debate_analyzer.api
   ```

   The API runs at **http://127.0.0.1:8000**.

2. Start the frontend (in another terminal, from repository root):

   ```bash
   cd frontend && npm run dev
   ```

   Open **http://localhost:5173** (or the URL Vite prints). You get hot reload for frontend changes.

**Option B – Production-like:** Build the frontend and serve it from FastAPI:

```bash
cd frontend && npm run build && cd ..
cp -r frontend/dist/* src/debate_analyzer/api/static/
poetry run python -m debate_analyzer.api
```

Then open **http://127.0.0.1:8000**. No separate Vite server.

### URLs

| URL | Description | Auth |
|-----|-------------|------|
| `/` | Public: speaker list (Vue SPA). | None |
| `/speakers/<id>` | Public: speaker detail and statistics (Vue SPA). | None |
| `/admin` | Admin: register transcripts, open transcript, navigate to annotation. | HTTP Basic (ADMIN_USERNAME / ADMIN_PASSWORD) |
| `/admin/speakers` | Admin: manage speaker profiles (add, edit, delete). | HTTP Basic |
| `/admin/annotate?transcript_id=...` | Admin: assign speaker IDs to speaker profiles for a transcript. | HTTP Basic |
| `/docs` | OpenAPI (Swagger) documentation. | None |
| `/api/speakers` | Public API: list speaker profiles. | None |
| `/api/speakers/{id_or_slug}` | Public API: get speaker profile and stats. | None |
| `/api/admin/*` | Admin API: list/get transcripts, register transcript, speaker CRUD, update speaker mappings. | HTTP Basic |

---

## Build for production (Docker)

The **Dockerfile.webapp** uses a multi-stage build: it builds the Vue app (Node) then copies `frontend/dist` into the image at `src/debate_analyzer/api/static/`. No need to build the frontend on the host first. From the repository root:

```bash
docker build -f Dockerfile.webapp -t debate-analyzer-webapp .
```

The image serves the API and the SPA from the same process. If you do not have `frontend/package-lock.json`, the Docker build runs `npm install` (otherwise `npm ci`) before `npm run build`.

---

## Deploy on AWS

The web app can be deployed to AWS using the **Web app stack** (ECS Fargate, RDS, ALB). See:

- [AWS_SETUP.md](AWS_SETUP.md) — Step-by-step setup; Part 2 covers the web app stack and variables.
- [ARCHITECTURE_AWS.md](ARCHITECTURE_AWS.md) — AWS deployment architecture.
- [deploy/terraform-webapp/README.md](../deploy/terraform-webapp/README.md) — Terraform quick reference.

The ECS task receives `DATABASE_URL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` from Secrets Manager; the task role has read-only access to the S3 bucket (from the Batch stack) so the app can load transcripts by S3 URI.

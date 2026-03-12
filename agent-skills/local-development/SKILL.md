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

## Downloading transcripts from AWS for local development

Sync all transcript artifacts (raw transcripts, postprocessed transcripts, stats JSON, and parquets) from the batch S3 bucket into `./data/<job-id>/transcripts/` so the local layout mirrors AWS (`jobs/<job-id>/transcripts/`). The webapp and tools can then use local files (e.g. register via `file://` or paths under `./data/<job-id>/transcripts/`).

### Prerequisites

- AWS CLI installed and configured (credentials with S3 read access to the bucket).
- Bucket name: from Batch Terraform, e.g. `source deploy/set-deploy-secrets.sh && cd deploy/terraform && terraform output -raw s3_bucket_name` (if Terraform state requires auth, run `source deploy/set-deploy-secrets.sh` in the same shell as below).
- At least one job ID whose transcripts to sync.

### Single job (recommended)

From repo root:

```bash
mkdir -p data/<JOB_ID>/transcripts
aws s3 sync s3://<BUCKET>/jobs/<JOB_ID>/transcripts/ ./data/<JOB_ID>/transcripts/
```

Replace `<BUCKET>` and `<JOB_ID>`. This pulls all of: `*_transcription_raw.json`, `*_transcription.json`, `*_speaker_stats.parquet`, `*_transcript_stats.json` (and any `*_llm_analysis.json`) for that job.

**One-liner** (bucket from Terraform; replace `<JOB_ID>`):

```bash
BUCKET=$(cd deploy/terraform && terraform output -raw s3_bucket_name) && mkdir -p data/<JOB_ID>/transcripts && aws s3 sync s3://$BUCKET/jobs/<JOB_ID>/transcripts/ ./data/<JOB_ID>/transcripts/
```

If Terraform state requires auth, run `source deploy/set-deploy-secrets.sh` in the same shell before the above.

### All jobs (optional)

List job IDs:

```bash
aws s3api list-objects-v2 --bucket <BUCKET> --prefix "jobs/" --delimiter "/" --query 'CommonPrefixes[*].Prefix' --output text
```

For each job ID, sync to `./data/<JOB_ID>/transcripts/`:

```bash
aws s3 sync s3://<BUCKET>/jobs/<JOB_ID>/transcripts/ ./data/<JOB_ID>/transcripts/
```

To sync all jobs in one go (replace `<BUCKET>`; job IDs from the list command above):

```bash
for JOB in $(aws s3api list-objects-v2 --bucket <BUCKET> --prefix "jobs/" --delimiter "/" --query 'CommonPrefixes[*].Prefix' --output text | tr '\t' '\n' | sed 's|jobs/||;s|/$||'); do mkdir -p "data/$JOB/transcripts" && aws s3 sync "s3://<BUCKET>/jobs/$JOB/transcripts/" "./data/$JOB/transcripts/"; done
```

When registering in the webapp, use paths like `file://$(pwd)/data/<JOB_ID>/transcripts/<stem>_transcription.json`.

### After download

Run the webapp and register transcripts using local URIs, e.g. `file://$(pwd)/data/<JOB_ID>/transcripts/<stem>_transcription.json` (replace `<JOB_ID>` and `<stem>`). The app will load `_speaker_stats.parquet` and `_transcript_stats.json` alongside the transcript when present.

### URLs

- `/` — speaker list
- `/speakers/<id>` — speaker detail
- `/admin` — register transcripts, annotate
- `/docs` — API docs

For more on env vars, database, and deployment, see [doc/WEBAPP.md](../../doc/WEBAPP.md) and [doc/HOWTO.md](../../doc/HOWTO.md).

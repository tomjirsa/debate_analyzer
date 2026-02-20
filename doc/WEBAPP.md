# Web App (Speaker Profiles and Statistics)

The Debate Analyzer web app provides a database of **speaker profiles**, **transcript registration** (from S3 or local paths), and **speaker annotation** (mapping transcript speaker IDs to profiles). Public pages show speaker list and per-speaker statistics.

---

## What It Does

- **Speaker profiles:** Create and manage speaker entities (name, slug, optional metadata).
- **Transcript registration:** Register transcripts by S3 URI (e.g. `s3://bucket/jobs/job-id/transcripts/file.json`) or local file path (e.g. `file:///path/to/transcription.json`). The app loads the JSON and stores segments and metadata.
- **Speaker annotation:** In the admin UI, open a transcript and assign transcript speaker IDs (e.g. `SPEAKER_00`, `SPEAKER_01`) to existing speaker profiles. This links transcript segments to profiles for statistics.
- **Public stats:** Public API and pages list speakers and show per-speaker statistics (e.g. number of transcripts, total segments, speaking time) derived from registered transcripts and annotations.

---

## Run Locally

### Install

Install the web app extra (or both transcribe and webapp for full local dev):

```bash
poetry install --extras webapp
# or
poetry install --extras transcribe --extras webapp
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection URL. | SQLite file `debate_analyzer.db` in the current working directory. |
| `ADMIN_USERNAME` | HTTP Basic auth username for `/admin` and `/api/admin/*`. | If unset, admin routes may be disabled or accept any credentials depending on implementation. |
| `ADMIN_PASSWORD` | HTTP Basic auth password for admin. | — |

For local development, SQLite is sufficient. For production (e.g. on AWS), use PostgreSQL and set `DATABASE_URL` (the ECS task definition injects it).

**Example (optional admin auth):**

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=admin
```

### Start the Server

From the repository root:

```bash
poetry run python -m debate_analyzer.api
```

The app runs with uvicorn on **http://127.0.0.1:8000** (reload enabled for development).

### URLs

| URL | Description | Auth |
|-----|-------------|------|
| `/` | Public: speaker list (static page). | None |
| `/speakers/<id>` | Public: speaker detail and statistics (static page). | None |
| `/admin` | Admin: register transcripts, open transcript, navigate to annotation. | HTTP Basic (ADMIN_USERNAME / ADMIN_PASSWORD) |
| `/admin/annotate?transcript_id=...` | Admin: assign speaker IDs to speaker profiles for a transcript. | HTTP Basic |
| `/docs` | OpenAPI (Swagger) documentation. | None |
| `/api/speakers` | Public API: list speaker profiles. | None |
| `/api/speakers/{id_or_slug}` | Public API: get speaker profile and stats. | None |
| `/api/admin/*` | Admin API: list/get transcripts, register transcript, update speaker mappings. | HTTP Basic |

---

## Deploy on AWS

The web app can be deployed to AWS using the **Web app stack** (ECS Fargate, RDS, ALB). See:

- [AWS_SETUP.md](AWS_SETUP.md) — Step-by-step setup; Part 2 covers the web app stack and variables.
- [ARCHITECTURE_AWS.md](ARCHITECTURE_AWS.md) — AWS deployment architecture.
- [deploy/terraform-webapp/README.md](../deploy/terraform-webapp/README.md) — Terraform quick reference.

The ECS task receives `DATABASE_URL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` from Secrets Manager; the task role has read-only access to the S3 bucket (from the Batch stack) so the app can load transcripts by S3 URI.

---
name: local-development
description: Instructions for running and developing the Debate Analyzer app locally. Use when the user asks how to run the webapp locally, start the API or frontend, or perform local development setup.
---

# Local Development

This skill is the single entrypoint for local development tasks. It routes to nested reference documents inside this skill.

## Routing guide

### Run the webapp locally

1. **Ask** the user this question:

`"Do you want to run the webapp with an entirely new database (fresh, no data) or use the current database (existing data)?"`

2. Then follow `references/web-app/local-run.md` for environment setup, prerequisites, and running the API/frontend.

3. If the user asks how to stop the servers, follow `references/web-app/shutdown.md`.

### Download transcripts from AWS for local development

1. Follow `references/aws-transcripts/download.md` to sync artifacts from S3 into `./data/<job-id>/transcripts/`.

2. Follow `references/aws-transcripts/after-download.md` to register the downloaded transcripts in the webapp.

### Upload local data from `./data` into the DB

1. Follow `references/data-upload/upload-local-data-to-db.md` to:
   - scan `./data/*/transcripts/*_transcription.json`,
   - register transcripts into the DB,
   - auto-create dummy speaker profiles for diarization labels,
   - import companion stats artifacts when present.

### API / Web app URLs

Follow `references/urls.md`.

## Optional helper scripts (if the user wants script-based commands)

This skill may include wrappers under `scripts/`:

- `scripts/start-api.sh`
- `scripts/start-frontend.sh`
- `scripts/stop-webapp.sh`

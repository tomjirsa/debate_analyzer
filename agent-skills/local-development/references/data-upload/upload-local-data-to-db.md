# Upload Local Data Into DB

Use this to auto-populate the local SQLite database from files on disk under:

`./data/*/transcripts/*_transcription.json`

The uploader will:

- Register transcripts (segments + empty speaker mappings) into the DB
- Import companion artifacts when present:
  - `*_speaker_stats.parquet`
  - `*_transcript_stats.json`
  - (optionally) `*_llm_analysis.json`
- Create dummy `SpeakerProfile` records for diarization labels (e.g. `SPEAKER_00`, `SPEAKER_01`)
- Auto-assign transcript speaker mappings so the UI can display speaker names
- Seed default `stat-definitions` if none exist (so speaker stats panels have metric groups)

## Run (recommended)

From repo root:

```bash
bash agent-skills/local-development/scripts/upload-local-data-to-db.sh
```

This uses the current database (does not set `DATABASE_URL`).

## Optional flags

- Import LLM analysis too:

```bash
bash agent-skills/local-development/scripts/upload-local-data-to-db.sh --import-llm-analysis
```

- Upload into a different content group:

```bash
bash agent-skills/local-development/scripts/upload-local-data-to-db.sh --group-slug <slug> --group-name "<name>"
```

- Disable stat-definition seeding:

```bash
bash agent-skills/local-development/scripts/upload-local-data-to-db.sh --no-seed-stat-definitions
```

## Notes

- The script is designed to be idempotent; re-running should not duplicate transcripts, and should re-apply mappings for diarization speakers.
- The default group slug is `default` (the script will create it if missing).


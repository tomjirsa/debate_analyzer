# AWS Transcripts: After Download

After downloading transcripts, run the webapp and register transcripts using local URIs, e.g.:

`file://$(pwd)/data/<JOB_ID>/transcripts/<stem>_transcription.json`

(replace `<JOB_ID>` and `<stem>`).

The app will load `_speaker_stats.parquet` and `_transcript_stats.json` alongside the transcript when present.


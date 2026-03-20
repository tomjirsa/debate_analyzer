# AWS Transcripts: Download for Local Development

Sync all transcript artifacts (raw transcripts, postprocessed transcripts, stats JSON, and parquets) from the batch S3 bucket into:

`./data/<job-id>/transcripts/`

This makes the local layout mirror AWS (`jobs/<job-id>/transcripts/`), so the webapp and tools can use local files (e.g. register via `file://` or paths under `./data/<job-id>/transcripts/`).

## Prerequisites

- AWS CLI installed and configured (credentials with S3 read access to the bucket).
- Bucket name: from Batch Terraform, e.g.
  `source deploy/set-deploy-secrets.sh && cd deploy/terraform && terraform output -raw s3_bucket_name`
  (if Terraform state requires auth, run `source deploy/set-deploy-secrets.sh` in the same shell as below).
- At least one job ID whose transcripts to sync.

## Single job (recommended)

From repo root:

```bash
mkdir -p data/<JOB_ID>/transcripts
aws s3 sync s3://<BUCKET>/jobs/<JOB_ID>/transcripts/ ./data/<JOB_ID>/transcripts/
```

Replace `<BUCKET>` and `<JOB_ID>`.

This pulls all of:

- `*_transcription_raw.json`
- `*_transcription.json`
- `*_speaker_stats.parquet`
- `*_transcript_stats.json`
- (and any `*_llm_analysis.json`)

for that job.

**One-liner** (bucket from Terraform; replace `<JOB_ID>`):

```bash
BUCKET=$(cd deploy/terraform && terraform output -raw s3_bucket_name) && mkdir -p data/<JOB_ID>/transcripts && aws s3 sync s3://$BUCKET/jobs/<JOB_ID>/transcripts/ ./data/<JOB_ID>/transcripts/
```

If Terraform state requires auth, run `source deploy/set-deploy-secrets.sh` in the same shell before the above.

## All jobs (optional)

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


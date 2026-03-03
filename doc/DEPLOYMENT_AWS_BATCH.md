# Deploying Debate Analyzer to AWS Batch (GPU)

This guide describes how to run the debate-analyzer pipeline on AWS Batch: you can either run a **single job** (download + transcribe) or **two separate jobs** (download to S3, then transcribe from S3). All infrastructure is provisioned with **Terraform**; the Docker image is built and pushed by **GitHub Actions**.

## Overview

- **Single job (full pipeline):** Submit a video URL; one job downloads the video, uploads to S3, transcribes with GPU, and uploads transcripts. Uses the GPU queue and job definition `debate-analyzer-job`.
- **Two jobs (recommended for reusing downloads):**
  - **Job 1 (download):** Submit a video URL; downloads and uploads to `s3://<bucket>/jobs/<job-id>/videos/`. Runs on CPU (cheaper). Use `submit-download-job.sh`.
  - **Job 2 (transcribe):** Submit an S3 prefix where the video already lives; transcribes and uploads to `s3://<bucket>/jobs/<path>/transcripts/`. Runs on GPU. Use `submit-transcribe-job.sh`.
- **Output (S3):** Downloaded video and optional subtitles under `s3://<bucket>/jobs/<job-id>/videos/`; transcription under `s3://<bucket>/jobs/<job-id>/transcripts/`. The transcribe job writes **`*_transcription_raw.json`**; the optional transcript postprocess job (when used) reads raw and writes **`*_transcription.json`** in the same prefix. Downstream jobs (stats, LLM analysis) use `*_transcription.json`.
- **Job 5 (transcript postprocess):** Optional. After transcribe, run transcript postprocess (Ollama) to correct grammar/ASR errors in raw transcripts. Use `./deploy/scripts/submit-jobs/submit-transcript-postprocess-job.sh <transcripts_s3_uri_or_prefix>`. The job reads **`*_transcription_raw.json`** and writes **`*_transcription.json`** in the same S3 prefix; it uses the same LLM image and GPU queue as Job 4. You can then run LLM analysis (Job 4) on the resulting `*_transcription.json`.
- **Job 4 (LLM analysis):** Optional. After transcribe (and optionally postprocess), run LLM analysis on transcript(s) to get main topics, per-topic summaries, and per-speaker contributions. Uses a **dedicated LLM image** (Ollama; see [LLM_ANALYSIS.md](LLM_ANALYSIS.md)). Use `submit-llm-analysis-job.sh`; the job runs on the **GPU queue**.
- **Secrets:** HuggingFace token is stored in AWS Secrets Manager and injected into the transcribe job (and full-pipeline job). The download and LLM analysis jobs do not need it (Qwen2 is public).
- **Cost:** CPU compute environment scales to zero when idle; GPU same. Using two jobs lets you re-run transcription without re-downloading.

## 1. Terraform setup and variables

### Prerequisites

- [Terraform](https://www.terraform.io/downloads) >= 1.0
- AWS CLI configured (or environment variables / profile) with permissions to create the resources below
- A [HuggingFace](https://huggingface.co) account and token, with [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) terms accepted

### Variables

All provisioning is in `deploy/terraform/`. Required variable:

- **`hf_token`** – Your HuggingFace token (sensitive). Provide via:
  - `export TF_VAR_hf_token="your_token"` before `terraform apply`, or
  - A `terraform.tfvars` file (do **not** commit it), or
  - A secret backend (e.g. Vault)

Optional variables (see `deploy/terraform/variables.tf`): `aws_region`, `name_prefix`, `ecr_image_tag`, `yt_cookies_secret_arn`, `batch_compute_instance_types`, `batch_min_vcpus`, `batch_max_vcpus`, `batch_cpu_instance_types`, `batch_cpu_min_vcpus`, `batch_cpu_max_vcpus`, `vpc_id`, `subnet_ids`, `use_spot`.

## 2. Terraform apply and what it creates

From the repository root:

```bash
cd deploy/terraform
terraform init
terraform plan   # review
terraform apply  # type yes when prompted
```

Terraform creates:

| Resource | Purpose |
|----------|---------|
| **Secrets Manager** secret | Stores the HuggingFace token; Batch injects it as `HF_TOKEN` into the container. |
| **S3** bucket | Holds downloaded videos and transcripts (prefix: `jobs/<job-id>/videos/` and `jobs/<job-id>/transcripts/`). |
| **IAM** roles | Job role (S3 + Secrets Manager), execution role (ECR + CloudWatch), instance role (for Batch compute EC2). |
| **ECR** repository | Holds the debate-analyzer Docker image (pushed by CI). |
| **Batch** compute environment (GPU) | GPU (e.g. g4dn.xlarge), min 0 / max 256 vCPUs. |
| **Batch** compute environment (CPU) | CPU (e.g. c5.xlarge), for download and stats jobs; min 0 / max 64 vCPUs. |
| **Batch** job queues | GPU queue (full pipeline + transcribe job); CPU queue (download and stats job). |
| **Batch** job definitions | Full pipeline (GPU); download-only (CPU, no HF token); transcribe-only (GPU, reads video from S3). |
| **CloudWatch** log group | Container logs from each job. |

After `apply`, note the outputs (e.g. `terraform output`): you will need **job queue name**, **job definition name**, and **bucket name** to submit jobs and find outputs.

## 3. Building and pushing the image (CI)

The Docker image is built and pushed to ECR by the **GitHub Actions** workflow `.github/workflows/build-push-ecr.yml` on push to `main` (or via `workflow_dispatch`).

### GitHub configuration

1. **AWS credentials for GitHub Actions** (choose one):
   - **OIDC (recommended):** In AWS IAM, add an OIDC identity provider for `https://token.actions.githubusercontent.com`, then create a role that trusts that provider and has ECR permissions (`GetAuthorizationToken`, `PutImage`, `InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`). In the repo: **Settings → Secrets and variables → Actions**: add secret `AWS_ROLE_ARN` with that role’s ARN.
   - **Static credentials:** Add secrets `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (and optionally `AWS_REGION`). Then change the workflow to use `aws-actions/configure-aws-credentials@v4` with `aws-access-key-id` / `aws-secret-access-key` instead of `role-to-assume`.

2. **Region:** Set variable **AWS_REGION** (e.g. `eu-central-1`) under **Settings → Variables** if you don’t use the default in the workflow.

3. Push to `main` (or run the workflow manually). The workflow builds the image from the repo root `Dockerfile` and pushes it to the ECR repository created by Terraform (repository name: `debate-analyzer`, tag: `latest` by default).

### Building and pushing locally

If you prefer to build and push from your machine:

```bash
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<region>.amazonaws.com
docker build -t <account_id>.dkr.ecr.<region>.amazonaws.com/debate-analyzer:latest .
docker push <account_id>.dkr.ecr.<region>.amazonaws.com/debate-analyzer:latest
```

Use the same region and account as Terraform; the ECR repository URL is in Terraform output `ecr_repository_url`.

## 4. Submitting a job (VIDEO_URL and OUTPUT_S3_PREFIX)

After the image is in ECR, submit a Batch job with container environment variables **VIDEO_URL** and **OUTPUT_S3_PREFIX**. The pipeline wrapper uses **AWS_BATCH_JOB_ID** (injected by Batch) to write each job’s outputs under a unique path.

Using Terraform outputs:

```bash
QUEUE=$(cd deploy/terraform && terraform output -raw batch_job_queue_name)
DEFN=$(cd deploy/terraform && terraform output -raw batch_job_definition_name)
BUCKET=$(cd deploy/terraform && terraform output -raw s3_bucket_name)
REGION=$(cd deploy/terraform && terraform output -raw aws_region)

aws batch submit-job \
  --job-name "debate-analyzer-$(date +%s)" \
  --job-queue "$QUEUE" \
  --job-definition "$DEFN" \
  --container-overrides "{\"environment\":[{\"name\":\"VIDEO_URL\",\"value\":\"https://www.youtube.com/watch?v=YOUR_VIDEO_ID\"},{\"name\":\"OUTPUT_S3_PREFIX\",\"value\":\"s3://$BUCKET/jobs\"}]}" \
  --region "$REGION"
```

Replace `YOUR_VIDEO_ID` with the YouTube video ID. The job will:

1. Download the video (and optional subtitles) in AWS.
2. Upload them to `s3://<bucket>/jobs/<job-id>/videos/`.
3. Transcribe with GPU and speaker diarization.
4. Upload transcription (and optionally audio) to `s3://<bucket>/jobs/<job-id>/transcripts/`.

Alternatively, use the helper script from the repo root: `./deploy/scripts/submit-jobs/submit-job.sh "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"`.

## 4b. Two-job flow: download then transcribe

You can split the pipeline into two Batch jobs so you can re-use an already-downloaded video (e.g. run transcription again with different settings without re-downloading).

### Job 1: Download (CPU)

- **Environment:** `VIDEO_URL`, `OUTPUT_S3_PREFIX` (e.g. `s3://<bucket>/jobs`). Batch injects `AWS_BATCH_JOB_ID`; outputs go under `OUTPUT_S3_PREFIX/<job-id>/videos/`.
- **Queue:** CPU queue (`batch_job_queue_cpu_name`).
- **Job definition:** `batch_job_definition_download_name`.

From the repo root:

```bash
./deploy/scripts/submit-jobs/submit-download-job.sh "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

Note the **job ID** from the output (e.g. `abc12345-6789-...`). When the job completes, the video is at `s3://<bucket>/jobs/<job-id>/videos/`.

### Job 2: Transcribe (GPU)

- **Environment:** `VIDEO_S3_PREFIX` (S3 prefix containing the video, e.g. `s3://<bucket>/jobs/<job-id>/videos/`), `OUTPUT_S3_PREFIX` (base prefix for transcripts, e.g. `s3://<bucket>/jobs/<job-id>`). Transcripts are written to `OUTPUT_S3_PREFIX/transcripts/`.
- **Queue:** GPU queue (`batch_job_queue_name`).
- **Job definition:** `batch_job_definition_transcribe_name`.

From the repo root (replace `<job-id>` with the download job ID):

```bash
BUCKET=$(cd deploy/terraform && terraform output -raw s3_bucket_name)
./deploy/scripts/submit-jobs/submit-transcribe-job.sh "s3://$BUCKET/jobs/<job-id>/videos"
```

Or with explicit output prefix:

```bash
./deploy/scripts/submit-jobs/submit-transcribe-job.sh "s3://$BUCKET/jobs/<job-id>/videos" "s3://$BUCKET/jobs/<job-id>"
```

The transcribe job syncs the video from S3 to the container, runs Whisper + pyannote, and uploads transcripts to `s3://<bucket>/jobs/<job-id>/transcripts/`.

### Job 3: Speaker stats (CPU)

- **When to run:** After the transcribe job has written transcript JSON files to the job folder. This job reads those JSON files, computes per-speaker statistics per transcript (total time, segment count, word count, words per minute, turn count, shortest/longest talk, first/last speaker, share of time/words, etc.), and writes `<stem>_speaker_stats.parquet` next to each `<stem>_transcription.json` in the same S3 prefix. If the transcript JSON includes a top-level `duration` (seconds), the job also computes each speaker’s share of total speaking time; otherwise that field is omitted.
- **Environment:** `TRANSCRIPTS_S3_PREFIX` (S3 prefix to the `transcripts/` folder, e.g. `s3://<bucket>/jobs/<job-id>/transcripts`).
- **Queue:** CPU queue (`batch_job_queue_cpu_name`).
- **Job definition:** `batch_job_definition_stats_name`.

From the repo root (replace `<job-id>` with the transcribe job ID):

```bash
BUCKET=$(cd deploy/terraform && terraform output -raw s3_bucket_name)
./deploy/scripts/submit-jobs/submit-stats-job.sh "s3://$BUCKET/jobs/<job-id>/transcripts"
```

Parquet files are written under the same prefix (e.g. `.../transcripts/foo_speaker_stats.parquet`). When you register a transcript from S3 in the web app, the app will load speaker stats from the corresponding parquet file (if present) and store them in the database for display.

**Local development:** You can run the stats job against a local directory of transcript JSONs (e.g. after running the transcriber locally). Set `TRANSCRIPTS_PREFIX` or `TRANSCRIPTS_S3_PREFIX` to a local path or `file://` URI pointing to a directory that contains `*_transcription.json` files; the job will write `<stem>_speaker_stats.parquet` into the same directory. Example:

```bash
# From repo root, after producing transcripts in data/transcripts/
export TRANSCRIPTS_PREFIX=./data/transcripts
python -m debate_analyzer.batch.stats_job
```

## 5. Where downloaded videos and transcripts land in S3

- **Downloaded video and subtitles:** `s3://<bucket>/jobs/<job-id>/videos/` and `s3://<bucket>/jobs/<job-id>/subtitles/`. Video files are stored **directly** under the `videos/` prefix (e.g. `.../videos/<filename>.mp4`), and subtitle files under `subtitles/` (e.g. `.../subtitles/<filename>.srt`).
- **Transcription JSON (and optionally extracted audio):** `s3://<bucket>/jobs/<job-id>/transcripts/`
- **Speaker stats parquet (after Job 3):** `s3://<bucket>/jobs/<job-id>/transcripts/<stem>_speaker_stats.parquet` (one file per transcript JSON).

`<job-id>` is the Batch job ID (e.g. from the `submit-job` output or the Batch console).

### Annotation page: loading video from S3 (CORS)

When you use the **admin annotation page** to annotate speakers, the page can load the video directly from S3 (automatically from the transcript’s S3 path, or via a manual S3 URI). The browser requests the video using a **presigned GET URL** (valid for 1 hour). For this to work, the S3 bucket must allow **CORS** requests from the web app’s origin.

- Add a CORS rule to the bucket with `AllowedOrigin` set to your web app’s origin (e.g. `https://your-app.example.com`) or a controlled wildcard if appropriate.
- Without CORS, the browser may block the video request and the player will not load.

The web app’s IAM role (or credentials) must have `s3:GetObject` on the bucket so it can generate presigned URLs.

## 6. Logs and troubleshooting

- **Batch job status:** AWS Console → Batch → Jobs, or `aws batch describe-jobs --jobs <job-id> --region <region>`.
- **Container logs:** CloudWatch Logs group `/aws/batch/debate-analyzer` (or the name in Terraform output); stream prefix `batch`.
- **Failed jobs:** Check the same log group for stderr; ensure `VIDEO_URL` and `OUTPUT_S3_PREFIX` are set and the HuggingFace token is valid and has accepted the pyannote model terms.

## 7. YouTube bot check (optional cookies)

The image includes Deno and EJS for YouTube. If you still see **"Sign in to confirm you're not a bot"** (common when running from AWS datacenter IPs), use a cookies file.

**Export:** Log into YouTube in a browser, then use an extension (e.g. [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)) to export cookies in Netscape format to a file (e.g. `cookies.txt`). Alternatively, you can export cookies from Chrome (e.g. JSON from an export extension or the Cookie header from the Network tab) and convert them with `python deploy/scripts/chrome_cookies_to_netscape.py [options] <input> -o cookies.txt`.

**Store:** Put the cookies in one of:

1. A **private** S3 object
2. An **AWS Secrets Manager** secret (secret value = raw cookies.txt content)
3. A file mounted into the container

**Use:**

- **Option A (Secrets Manager):**
  - **From a local file via Terraform:** Set the Terraform variable `yt_cookies_file_path` to the path to your `cookies.txt` (e.g. `./cookies.txt` or `~/cookies.txt`). Run `terraform apply`; Terraform will create the secret from the file and configure the job. Do not commit the cookies file. Terraform state will contain the secret value—use a remote backend with encryption and restrict access.
  - **Existing secret:** Create a secret in AWS (console or CLI) with the cookies content, then set the Terraform variable `yt_cookies_secret_arn` to the secret ARN (or pass `YT_COOKIES_SECRET_ARN` in container overrides). The entrypoint fetches the value and sets `YT_COOKIES_FILE` before the download step.
- **Option B (S3):** Set `YT_COOKIES_S3_URI` to the S3 URI (e.g. `s3://your-bucket/private/cookies.txt`). The entrypoint downloads it and sets `YT_COOKIES_FILE`.
- **Option C (direct path):** If the cookie file is provided by another mechanism (e.g. volume mount), set `YT_COOKIES_FILE` to the path inside the container.

**Security:** The cookie file is as sensitive as a browser session. Use a private bucket or Secrets Manager and least-privilege IAM. Do not commit or log the file.

## 8. Speaker profile photos (CloudFront + stable URLs)

Speaker profile photos are stored in the same S3 bucket under the prefix `speaker-photos/<group_id>/<speaker_id>.<ext>` (e.g. `speaker-photos/<uuid>/<uuid>.jpg`). They are delivered at **stable, non-expiring** public URLs via a **CloudFront** distribution that the Batch stack creates in front of the bucket (Origin Access Control).

- **Batch stack:** After `terraform apply`, the stack creates a CloudFront distribution and outputs `cloudfront_domain_name` and `cloudfront_speaker_photos_url` (e.g. `https://d123.cloudfront.net`). Configure **CORS** for the bucket if the web app origin needs to upload photos from the browser: set the variable `cors_allowed_origins` (e.g. `["https://your-webapp.example.com"]`) so that presigned PUT requests from the admin UI succeed.
- **Web app stack:** When applying or updating the web app Terraform stack, set `cloudfront_speaker_photos_url` to the Batch stack output (e.g. `https://d123.cloudfront.net`) so the app receives `SPEAKER_PHOTOS_BASE_URL`. Optionally set `speaker_photos_s3_bucket` if you use a different bucket for uploads; otherwise it defaults to `existing_s3_bucket_name`. Redeploy the web app so the ECS task gets these environment variables; then the API will return `photo_url` for speakers that have a `photo_key` set.

**Deployment order:** Apply the Batch stack first (to create CloudFront and bucket policy). Note the `cloudfront_speaker_photos_url` output. Apply or update the web app stack with `cloudfront_speaker_photos_url` (and optionally `speaker_photos_s3_bucket`), then deploy the app so migrations run and the new env vars are present.

## Summary

1. Set `TF_VAR_hf_token`, run `terraform init` and `terraform apply` in `deploy/terraform/`.
2. Configure GitHub Actions (OIDC or static AWS credentials) and push to `main` to build and push the image to ECR.
3. **Single job:** Use `./deploy/scripts/submit-jobs/submit-job.sh <video_url>` or `aws batch submit-job` with `VIDEO_URL` and `OUTPUT_S3_PREFIX=s3://<bucket>/jobs`.
4. **Two jobs:** Use `./deploy/scripts/submit-jobs/submit-download-job.sh <video_url>`, then `./deploy/scripts/submit-jobs/submit-transcribe-job.sh s3://<bucket>/jobs/<job-id>/videos` (see section 4b).
5. **Optional Job 3 (stats):** After transcribe, run `./deploy/scripts/submit-jobs/submit-stats-job.sh s3://<bucket>/jobs/<job-id>/transcripts` to generate per-speaker stats parquet in the same folder. When you register transcripts from S3 in the web app, stats are loaded from these parquet files into the database.
6. **Optional Job 5 (transcript postprocess):** After transcribe, run `./deploy/scripts/submit-jobs/submit-transcript-postprocess-job.sh s3://<bucket>/jobs/<job-id>/transcripts` (or a single `*_transcription_raw.json` URI). The job reads raw transcripts and writes `*_transcription.json`; then you can run Job 4 (LLM analysis) on those files.
7. Find outputs in S3 under `jobs/<job-id>/videos/` and `jobs/<job-id>/transcripts/`, and logs in CloudWatch under `/aws/batch/debate-analyzer`.
8. If YouTube shows "Sign in to confirm you're not a bot", use optional cookies (see section 7); set `YT_COOKIES_FILE`, `YT_COOKIES_S3_URI`, or `YT_COOKIES_SECRET_ARN` (or Terraform variable `yt_cookies_secret_arn`).
9. **Speaker photos:** After applying the Batch stack, set the web app variable `cloudfront_speaker_photos_url` to the Batch output and (optionally) `cors_allowed_origins` for the bucket; then apply/update the web app stack and redeploy the app (see section 8).

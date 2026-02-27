# LLM-based transcript analysis

This document describes how to run **LLM analysis** on transcripts: main topics, per-topic discussion summary, and per-speaker contributions. The analysis runs as a **one-time job** (e.g. after transcription) using a **dedicated LLM Docker image** and **AWS Batch** (GPU).

## Overview

- **Model:** Qwen2-1.5B-Instruct (default). Default context 8k; 1.5B fits 16 GB T4 (e.g. g4dn.2xlarge) comfortably. For 32k use a 24 GB+ GPU or set `LLM_MAX_MODEL_LEN`. LLM jobs use a dedicated queue.
- **Input:** Transcript JSON (from S3 or local), in the same format as the transcribe job output (`transcription` list with `speaker`, `text`, `start`, `end`).
- **Output:** JSON with `main_topics`, `topic_summaries`, `speaker_contributions`, written to S3 as `<stem>_llm_analysis.json` alongside the transcript, or imported into the DB via the admin API.
- **Chunking:** Long transcripts (over the configured context) are split into chunks for topic extraction; topics are merged and then summarized. All phases respect the context limit set by `LLM_MAX_MODEL_LEN`.

### Model cache (EFS)

The LLM job mounts a shared **EFS** volume at `/cache` and sets `HF_HOME=/cache`. The first job (or first run after the cache is empty) downloads the model from Hugging Face into EFS; subsequent jobs reuse that cache and do not re-download. The very first job (or first job in a new region/account) may be slower due to the initial download; later jobs start faster.

## 1. Build and push the LLM image

The LLM job uses a **separate image** (Option B) so the main app image stays small.

1. **Build** from the repo root:
   ```bash
   docker build -f Dockerfile.llm -t debate-analyzer-llm:latest .
   ```

2. **Tag and push** to the ECR repo created by Terraform:
   ```bash
   cd deploy/terraform
   ECR_LLM=$(terraform output -raw ecr_repository_llm_url)
   aws ecr get-login-password --region $(terraform output -raw aws_region) | \
     docker login --username AWS --password-stdin "${ECR_LLM%%/*}"
   docker tag debate-analyzer-llm:latest "$ECR_LLM:latest"
   docker push "$ECR_LLM:latest"
   ```

3. **Terraform** must be applied first so the `debate-analyzer-llm` ECR repository exists. The CPU job definition uses tag `latest`; the GPU job definition uses tag `latest-gpu`. For **GPU** jobs, build and push the GPU image: `docker build -f Dockerfile.llm.gpu -t debate-analyzer-llm:latest-gpu .` then push to the same ECR repo with tag `latest-gpu` (CI does this when Dockerfile.llm.gpu or LLM code changes).

## 2. Run the LLM analysis job

After transcripts exist in S3 (e.g. after the transcribe job). You can run on **CPU** (cheaper, slower) or **GPU** (faster; launches a GPU instance with 16 GB T4). Job uses Qwen2-1.5B and `LLM_MAX_MODEL_LEN=8192` by default. For 32k context use a 24 GB+ GPU and set `LLM_MAX_MODEL_LEN=32768`.

**CPU (default; no GPU instance):**
```bash
./deploy/scripts/submit-jobs/submit-llm-analysis-job.sh \
  s3://<bucket>/jobs/<job-id>/transcripts/<stem>_transcription.json
```

**GPU (faster; requires LLM GPU image pushed as `latest-gpu`):**
```bash
./deploy/scripts/submit-jobs/submit-llm-analysis-job.sh --gpu \
  s3://<bucket>/jobs/<job-id>/transcripts/<stem>_transcription.json
```
Or use `submit-llm-analysis-job-gpu.sh` with the same URI.

**All transcripts under a prefix:** Use the same script with the prefix; add `--gpu` for GPU:
```bash
./deploy/scripts/submit-jobs/submit-llm-analysis-job.sh --gpu \
  s3://<bucket>/jobs/<job-id>/transcripts
```

The job reads each `*_transcription.json`, runs the three-phase analysis (topics → topic summaries → speaker contributions), and writes `*_llm_analysis.json` to the same S3 prefix.

## 3. Environment variables (job)

| Variable | Description |
|----------|-------------|
| `TRANSCRIPT_S3_URI` | Single transcript JSON URI (s3:// or file). |
| `TRANSCRIPTS_S3_PREFIX` | S3 prefix; all `*_transcription.json` under it are processed. |
| `LLM_MODEL_ID` | Hugging Face model id (default: `Qwen/Qwen2-1.5B-Instruct`). |
| `LLM_MAX_MODEL_LEN` | Max context length (default: `8192`). Qwen2-1.5B fits 16 GB T4 easily. For 32k use a 24 GB+ GPU and set to `32768`. |
| `LLM_USE_GPU` | Set to `1` by the GPU job definition; selects Transformers GPU backend (CUDA). Omit or leave unset for CPU. |
| `MOCK_LLM` | Set to `1` to use a mock backend (no GPU; for testing). |
| `LLM_LOG_FULL` | Set to `1`, `true`, or `yes` to log full prompts and responses; otherwise they are truncated (see Logging below). Use only for dev/debug; full logs may include PII. |

### Logging (batch job)

The LLM batch job writes progress and, when running in batch, **each LLM request and response** to stderr with a `[LLM]` prefix so you can filter in CloudWatch. By default, prompts are truncated to 500 characters and responses to 1000 characters to limit noise and PII. Set **`LLM_LOG_FULL=1`** (or `true`/`yes`) to log full prompts and responses; use only in development or debugging, as they may contain transcript content.

## 4. Output schema

Each `_llm_analysis.json` file contains:

```json
{
  "main_topics": [
    { "id": "t1", "title": "short label", "description": "optional" }
  ],
  "topic_summaries": [
    { "topic_id": "t1", "summary": "Discussion outcome for this topic." }
  ],
  "speaker_contributions": [
    { "topic_id": "t1", "speaker_id_in_transcript": "SPEAKER_06", "summary": "Position or contribution." }
  ]
}
```

## 5. Import into the web app

To attach analysis to a transcript in the DB (for the admin UI or API):

- **From S3:** `POST /api/admin/transcripts/{transcript_id}/analysis/import` with body:
  `{ "source_uri": "s3://bucket/key/<stem>_llm_analysis.json", "model_name": "Qwen/Qwen2-1.5B-Instruct", "source": "batch" }`
- **Inline:** Same endpoint with body:
  `{ "result": { "main_topics": [...], "topic_summaries": [...], "speaker_contributions": [...] }, "model_name": "...", "source": "api" }`

Get the latest analysis: `GET /api/admin/transcripts/{transcript_id}/analysis`.

## 6. Chunking (long transcripts)

Transcripts longer than the configured context (see `LLM_MAX_MODEL_LEN`, default 8k tokens) are handled as follows:

- **Phase 1 (topics):** The flattened transcript is split into overlapping chunks (within the context limit). The LLM extracts topics per chunk; topics are merged and deduplicated by title.
- **Phase 2 (summaries):** For each topic, an excerpt of the transcript (truncated to the context limit) is used to generate the discussion summary.
- **Phase 3 (speaker contributions):** Same excerpt is used to summarize each speaker’s contribution per topic.

So chunking is **required** when the transcript exceeds the configured context; the runner enforces it automatically.

## 7. Local / testing

- **Mock backend:** Run the batch module with `MOCK_LLM=1` and `TRANSCRIPT_S3_URI` or `TRANSCRIPTS_S3_PREFIX` pointing to a local file or directory (e.g. `file:///path/to/transcript.json`). No GPU or vLLM needed.
- **Analysis module:** The `debate_analyzer.analysis` package can be tested with `MockLLMBackend` in unit tests; see `tests/`.

## 8. Related

- **AWS Batch (transcribe, download, stats):** [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md)
- **Terraform:** LLM job definition and ECR repo are in `deploy/terraform/` (job definition `debate-analyzer-job-llm-analysis`, ECR `debate-analyzer-llm`).

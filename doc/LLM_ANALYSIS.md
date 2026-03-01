# LLM-based transcript analysis

This document describes how to run **LLM analysis** on transcripts: main topics, per-topic discussion summary, and per-speaker contributions. The analysis runs as a **one-time job** (e.g. after transcription) using a **dedicated LLM Docker image** and **AWS Batch** (GPU).

## Overview

- **Model:** Qwen2-1.5B-Instruct (default). Default context 8k; 1.5B fits 16 GB T4 (e.g. g4dn.2xlarge) comfortably. For 32k use a 24 GB+ GPU or set `LLM_MAX_MODEL_LEN`. LLM jobs use a dedicated queue.
- **Input:** Transcript JSON (from S3 or local), in the same format as the transcribe job output (`transcription` list with `speaker`, `text`, `start`, `end`).
- **Output:** JSON with `main_topics`, `topic_summaries`, `speaker_contributions`, written to S3 as `<stem>_llm_analysis.json` alongside the transcript, or imported into the DB via the admin API.
- **Chunking:** Long transcripts (over the configured context) are split into chunks for topic extraction; topics are merged and then summarized. The batch job passes `LLM_MAX_MODEL_LEN` into the runner so chunk and excerpt sizes respect the model context (with a reserve for prompt and reply). Phase 2 and Phase 3 use **topic-relevant excerpts** (keyword-based) when available.
- **Batched inference:** Phase 1, Phase 2, and Phase 3 each run as one or more batched GPU/CPU calls (multiple prompts per call) for better throughput. Batch size is limited by `LLM_BATCH_SIZE` (default 8) on GPU to avoid OOM.

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

3. **Terraform** must be applied first so the `debate-analyzer-llm` ECR repository exists. The CPU job definition uses tag `latest`; the GPU job definition uses tag `latest-gpu`. For **GPU** jobs, build and push the GPU image: `docker build -f Dockerfile.llm.gpu -t debate-analyzer-llm:latest-gpu .` then push to the same ECR repo with tag `latest-gpu` (CI does this when Dockerfile.llm.gpu or LLM code changes). For **Ollama on AWS Batch**, see section 2b below (build with `Dockerfile.llm.ollama`, tag `latest-ollama`).

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

### 2a. Running with Ollama (local)

You can run the same job **locally** with the model served by **Ollama** on the same machine. The job talks to Ollama over HTTP (default `http://localhost:11434`) via LangChain. No Transformers or GPU in the job process; Ollama uses the GPU if available.

**Prerequisites:**

- Ollama installed and running (e.g. `ollama serve` or `ollama run <model>`).
- Model pulled (e.g. `ollama pull qwen2.5:7b`).
- Install the LLM extra: `poetry install --extras llm`.

**Environment:**

- `LLM_BACKEND=ollama` (or `LLM_USE_OLLAMA=1`).
- `OLLAMA_HOST` (optional; default `http://localhost:11434`).
- `OLLAMA_MODEL` or `LLM_MODEL_ID` — Ollama model name (e.g. `qwen2.5:7b`, `llama3.2`).

**Example (single transcript):**

```bash
TRANSCRIPT_S3_URI=file:///path/to/foo_transcription.json \
LLM_BACKEND=ollama \
python -m debate_analyzer.batch.llm_analysis_job
```

Output is written next to the transcript as `foo_llm_analysis.json`.

### 2b. Running with Ollama on AWS Batch

You can run LLM analysis on **AWS Batch** using **Ollama** inside the same container: the entrypoint starts the Ollama daemon, then runs the Python job with `LLM_BACKEND=ollama` talking to localhost. Models are stored on the shared **EFS** volume at `/cache/ollama` so the first job pulls the model and later jobs reuse it.

**Prerequisites:**

- Terraform applied (Batch stack with EFS and GPU queue).
- Ollama image built and pushed to the `debate-analyzer-llm` ECR repo with tag `latest-ollama`.

**Build and push the Ollama image:**

```bash
docker build -f Dockerfile.llm.ollama -t debate-analyzer-llm:latest-ollama .
cd deploy/terraform
ECR_LLM=$(terraform output -raw ecr_repository_llm_url)
aws ecr get-login-password --region $(terraform output -raw aws_region) | \
  docker login --username AWS --password-stdin "${ECR_LLM%%/*}"
docker tag debate-analyzer-llm:latest-ollama "$ECR_LLM:latest-ollama"
docker push "$ECR_LLM:latest-ollama"
```

**Environment (set by job definition):** `LLM_BACKEND=ollama`, `OLLAMA_HOST=http://localhost:11434`, `OLLAMA_MODELS=/cache/ollama`, `OLLAMA_MODEL` (e.g. `qwen2.5:7b`), `LLM_MAX_MODEL_LEN=8192`. You can override `OLLAMA_MODEL` via container overrides when submitting.

**Example (single transcript or all under prefix):**

```bash
./deploy/scripts/submit-jobs/submit-llm-analysis-job-ollama.sh \
  s3://<bucket>/jobs/<job-id>/transcripts/<stem>_transcription.json
# Or all transcripts under prefix:
./deploy/scripts/submit-jobs/submit-llm-analysis-job-ollama.sh \
  s3://<bucket>/jobs/<job-id>/transcripts
```

The first job (or first per EFS cache) may be slower while the model is pulled; subsequent jobs reuse the EFS cache.

**Troubleshooting: "manifest unknown" / CannotPullImageManifestError**

This means the Batch job is trying to pull an image that does not exist (or not with the expected tag) in your ECR repo. The Ollama job definition uses the image **`debate-analyzer-llm:latest-ollama`** in the same ECR repo as the other LLM images.

1. **Ensure the image exists in ECR** (same account and region as your Batch stack). Either:
   - Run the **GitHub Actions** workflow **"Build and push to ECR"** (manual dispatch or push a change that triggers it). The workflow builds `Dockerfile.llm.ollama` and pushes to `debate-analyzer-llm:latest-ollama`.
   - Or build and push locally (see "Build and push the Ollama image" above).
2. **Verify** the image is present:
   ```bash
   aws ecr describe-images --repository-name debate-analyzer-llm --image-ids imageTag=latest-ollama --region $(terraform -chdir=deploy/terraform output -raw aws_region)
   ```
   Or use the full image URI from Terraform: `terraform -chdir=deploy/terraform output -raw ecr_image_uri_llm_ollama`.
3. **Region/account**: The workflow must push to the **same AWS account and region** as your Terraform deploy. In GitHub Actions, the region is set by the `AWS_REGION` input (default `eu-central-1`); it must match your Terraform `aws_region`.

## 3. Environment variables (job)

| Variable | Description |
|----------|-------------|
| `TRANSCRIPT_S3_URI` | Single transcript JSON URI (s3:// or file). |
| `TRANSCRIPTS_S3_PREFIX` | S3 prefix; all `*_transcription.json` under it are processed. |
| `LLM_MODEL_ID` | Hugging Face model id (default: `Qwen/Qwen2-1.5B-Instruct`). |
| `LLM_MAX_MODEL_LEN` | Max context length (default: `8192`). Qwen2-1.5B fits 16 GB T4 easily. For 32k use a 24 GB+ GPU and set to `32768`. |
| `LLM_USE_GPU` | Set to `1` by the GPU job definition; selects Transformers GPU backend (CUDA). Omit or leave unset for CPU. |
| `LLM_BATCH_SIZE` | Max prompts per GPU batch (default `2` for 16 GB GPUs). Use 4–8 on 24 GB+ if OOM does not occur. |
| `MOCK_LLM` | Set to `1` to use a mock backend (no GPU; for testing). |
| `LLM_BACKEND` | Set to `ollama` to use Ollama via LangChain (local). Omit for Transformers. |
| `LLM_USE_OLLAMA` | Set to `1`, `true`, or `yes` as alternative to `LLM_BACKEND=ollama`. |
| `OLLAMA_HOST` | Ollama API base URL (default: `http://localhost:11434`). Used when `LLM_BACKEND=ollama`. |
| `OLLAMA_MODELS` | Directory for Ollama model storage. On AWS Batch set to `/cache/ollama` (EFS). |
| `OLLAMA_MODEL` | Ollama model name (e.g. `qwen2.5:7b`). Fallback: `LLM_MODEL_ID`. Used when `LLM_BACKEND=ollama`. |
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

## 6. Chunking and excerpts (long transcripts)

The job sets chunk and excerpt size from `LLM_MAX_MODEL_LEN` (default 8k) so the model never receives more context than it supports.

- **Phase 1 (topics):** The flattened transcript is split into overlapping chunks (within the context limit). The LLM extracts topics per chunk; topics are merged and deduplicated by title.
- **Phase 2 (summaries):** For each topic, a **topic-relevant excerpt** is built by finding lines that mention the topic (from its title/description) and taking a window around them, truncated to the context limit. If no match is found, the start of the transcript is used. That excerpt is used to generate the discussion summary.
- **Phase 3 (speaker contributions):** The same per-topic excerpt is used to summarize each speaker’s contribution for that topic.

Chunking is **required** when the transcript exceeds the configured context; the runner enforces it automatically.

## 7. Local / testing

- **Mock backend:** Run the batch module with `MOCK_LLM=1` and `TRANSCRIPT_S3_URI` or `TRANSCRIPTS_S3_PREFIX` pointing to a local file or directory (e.g. `file:///path/to/transcript.json`). No GPU or vLLM needed.
- **Analysis module:** The `debate_analyzer.analysis` package can be tested with `MockLLMBackend` in unit tests; see `tests/`.

## 8. Related

- **AWS Batch (transcribe, download, stats):** [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md)
- **Terraform:** LLM job definition and ECR repo are in `deploy/terraform/` (job definition `debate-analyzer-job-llm-analysis`, ECR `debate-analyzer-llm`).

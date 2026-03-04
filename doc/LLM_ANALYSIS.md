# LLM-based transcript analysis

This document describes how to run **LLM analysis** on transcripts: main topics, per-topic discussion summary, and per-speaker contributions. The analysis runs as a **one-time job** (e.g. after transcription) using **Ollama** (or a mock backend for tests) and a **dedicated LLM Docker image** for **AWS Batch** (GPU).

## Overview

- **Backend:** **Ollama** only (production). Use `MOCK_LLM=1` for tests (no model required).
- **Model:** Ollama model name (e.g. `qwen2.5:7b` via `OLLAMA_MODEL` or `LLM_MODEL_ID`). Default context 8k; set `LLM_MAX_MODEL_LEN` as needed. On AWS Batch the job runs on the GPU queue.
- **Input:** Transcript JSON (from S3 or local), in the same format as the transcribe job output (`transcription` list with `speaker`, `text`, `start`, `end`).
- **Output:** JSON with `main_topics`, `topic_summaries`, `speaker_contributions`, written to S3 as `<stem>_llm_analysis.json` alongside the transcript, or imported into the DB via the admin API. Each item in `main_topics` may include `start_sec` and `end_sec` (seconds from video start) for linking to video playback; these are derived from the transcript segment timestamps that cover the topic’s conversation.
- **Chunking:** Long transcripts (over the configured context) are split into chunks for topic extraction; topics are merged and then summarized. The job uses `LLM_MAX_MODEL_LEN` and Ollama-specific reserves so chunk and excerpt sizes fit in context. Phase 2 and Phase 3 use **topic-relevant excerpts** (keyword-based) when available.

### Output schema

The `*_llm_analysis.json` file (and the `result` field when imported into the DB) contains:

- **`main_topics`**: List of topic objects. Each has `id`, `title`, `description`, `keywords`, and optionally **`start_sec`** and **`end_sec`** (floats, seconds from video start). Use `start_sec`/`end_sec` to seek the video to the topic’s conversation; they are omitted or `null` when the range cannot be computed.
- **`topic_summaries`**: List of `{ "topic_id", "summary" }`.
- **`speaker_contributions`**: List of `{ "topic_id", "speaker_id_in_transcript", "summary" }`.

### Model cache (EFS, AWS Batch)

On AWS Batch the LLM job mounts a shared **EFS** volume at `/cache`; Ollama stores models at `/cache/ollama` (`OLLAMA_MODELS`). The first job pulls the model; subsequent jobs reuse the cache.

## 1. Build and push the LLM image (AWS)

The LLM job uses a **separate image** so the main app image stays small. Only the **Ollama** image is used.

1. **Build** from the repo root:
   ```bash
   docker build -f Dockerfile.llm.ollama -t debate-analyzer-llm:latest-ollama .
   ```

2. **Tag and push** to the ECR repo created by Terraform:
   ```bash
   cd deploy/terraform
   ECR_LLM=$(terraform output -raw ecr_repository_llm_url)
   aws ecr get-login-password --region $(terraform output -raw aws_region) | \
     docker login --username AWS --password-stdin "${ECR_LLM%%/*}"
   docker tag debate-analyzer-llm:latest-ollama "$ECR_LLM:latest-ollama"
   docker push "$ECR_LLM:latest-ollama"
   ```

3. **Terraform** must be applied first so the `debate-analyzer-llm` ECR repository exists. The LLM job definition uses the image with tag `latest-ollama`. CI (GitHub Actions) can build and push this image when LLM code or the Dockerfile changes.

## 2. Run the LLM analysis job

After transcripts exist in S3 (e.g. after the transcribe job). The job uses **Ollama** (locally or on AWS Batch).

**On AWS Batch (single transcript or prefix):**
```bash
./deploy/scripts/submit-jobs/submit-llm-analysis-job.sh \
  s3://<bucket>/jobs/<job-id>/transcripts/<stem>_transcription.json
# Or all transcripts under a prefix:
./deploy/scripts/submit-jobs/submit-llm-analysis-job.sh \
  s3://<bucket>/jobs/<job-id>/transcripts
```

The job reads each `*_transcription.json`, runs the three-phase analysis (topics → topic summaries → speaker contributions), and writes `*_llm_analysis.json` to the same S3 prefix.

### 2a. Running with Ollama (local)

You can run the same job **locally** with the model served by **Ollama** on the same machine. The job talks to Ollama over HTTP (default `http://localhost:11434`) via LangChain. Ollama uses the GPU if available.

**Prerequisites:**

- Ollama installed and running (e.g. `ollama serve` or `ollama run <model>`).
- Model pulled (e.g. `ollama pull qwen2.5:7b`).
- Install the LLM extra: `poetry install --extras llm`.

**Environment:**

- `OLLAMA_HOST` (optional; default `http://localhost:11434`).
- `OLLAMA_MODEL` or `LLM_MODEL_ID` — Ollama model name (e.g. `qwen2.5:7b`, `llama3.2`).
- `LLM_MAX_MODEL_LEN` — Context length (default `8192`). The Ollama backend passes this as `num_ctx`; use at least `4096` to avoid "truncating input prompt". For Batch, the entrypoint also sets `OLLAMA_CONTEXT_LENGTH` from this.

**If the server still logs "truncating input prompt" (limit=2048):** Many Ollama setups only apply a larger context when the **server** is started with it. Stop `ollama serve` and start it with the same value as your job, e.g. `OLLAMA_CONTEXT_LENGTH=4096 ollama serve` (or `8192` to match default `LLM_MAX_MODEL_LEN`). Then run the Python job as usual.

**Avoiding context truncation with Ollama:** With an 8192-token context, prompts can still overflow if chunk/excerpt sizing is optimistic. To avoid "truncating input prompt", you can set:

- **`LLM_OLLAMA_MAX_CONTENT_TOKENS`** (optional) — When set, used as the max content tokens for Phase 1 chunks and for excerpt sizing (e.g. `4000`) so prompt + reply fit in context.
- **`LLM_OLLAMA_MAX_EXCERPT_TOKENS`** (optional) — When set, Phase 2 and 3 excerpts are capped at this size (e.g. `3000`). If unset, the job uses a default (3000) when using Ollama.
- **`LLM_CHARS_PER_TOKEN`** (optional; default `4`) — Characters per token for estimation. Use `3` for safer sizing with Ollama/Czech (fewer characters per chunk, so real token count stays under limit).

Example: `LLM_OLLAMA_MAX_CONTENT_TOKENS=4000 LLM_CHARS_PER_TOKEN=3` (and optionally `LLM_OLLAMA_MAX_EXCERPT_TOKENS=3000`) helps keep each request under 8192.

**Example (single transcript):**

```bash
TRANSCRIPT_S3_URI=file:///path/to/foo_transcription.json \
OLLAMA_MODEL=qwen2.5:7b \
python -m debate_analyzer.batch.llm_analysis_job
```

Output is written next to the transcript as `foo_llm_analysis.json`.

### 2b. Running with Ollama on AWS Batch

You can run LLM analysis on **AWS Batch** using **Ollama** inside the same container: the entrypoint starts the Ollama daemon, then runs the Python job talking to localhost. Models are stored on the shared **EFS** volume at `/cache/ollama` so the first job pulls the model and later jobs reuse it.

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

**Environment (set by job definition):** `OLLAMA_HOST=http://localhost:11434`, `OLLAMA_MODELS=/cache/ollama`, `OLLAMA_MODEL` (e.g. `qwen2.5:7b`), `LLM_MAX_MODEL_LEN=8192`. You can override `OLLAMA_MODEL` via container overrides when submitting.

**Example (single transcript or all under prefix):**

```bash
./deploy/scripts/submit-jobs/submit-llm-analysis-job.sh \
  s3://<bucket>/jobs/<job-id>/transcripts/<stem>_transcription.json
# Or all transcripts under prefix:
./deploy/scripts/submit-jobs/submit-llm-analysis-job.sh \
  s3://<bucket>/jobs/<job-id>/transcripts
```

The first job (or first per EFS cache) may be slower while the model is pulled; subsequent jobs reuse the EFS cache.

**Troubleshooting: "manifest unknown" / CannotPullImageManifestError**

This means the Batch job is trying to pull an image that does not exist (or not with the expected tag) in your ECR repo. The LLM job definition uses the image **`debate-analyzer-llm:latest-ollama`** in the ECR repo.

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
| `MOCK_LLM` | Set to `1`, `true`, or `yes` to use a mock backend (no model; for testing). |
| `LLM_MAX_MODEL_LEN` | Max context length (default: `8192`). Passed to Ollama as `num_ctx`; use at least 4096 to avoid input truncation. On AWS Batch the entrypoint sets `OLLAMA_CONTEXT_LENGTH` from this. |
| `OLLAMA_HOST` | Ollama API base URL (default: `http://localhost:11434`). |
| `OLLAMA_MODELS` | Directory for Ollama model storage. On AWS Batch set to `/cache/ollama` (EFS). |
| `OLLAMA_MODEL` | Ollama model name (e.g. `qwen2.5:7b`). Fallback: `LLM_MODEL_ID`. |
| `LLM_MODEL_ID` | Fallback for `OLLAMA_MODEL` if unset (e.g. `qwen2.5:7b`). |
| `LLM_OLLAMA_MAX_CONTENT_TOKENS` | (Optional.) Max content tokens for chunks/excerpts (e.g. `4000`). Overrides the default reserve-based cap; helps avoid context truncation. |
| `LLM_OLLAMA_MAX_EXCERPT_TOKENS` | (Optional.) Phase 2 and 3 excerpts are capped at this size (e.g. `3000`). Default 3000 if unset. |
| `LLM_CHARS_PER_TOKEN` | (Optional; default `4`.) Characters per token for chunk/excerpt sizing. Use `3` for safer estimation with Ollama/Czech. |
| `LLM_LOG_FULL` | Set to `1`, `true`, or `yes` to log full prompts and responses; otherwise they are truncated (see Logging below). Use only for dev/debug; full logs may include PII. |

### Logging (batch job)

The LLM batch job writes progress and, when running in batch, **each LLM request and response** to stderr with a `[LLM]` prefix so you can filter in CloudWatch. By default, prompts are truncated to 500 characters and responses to 1000 characters to limit noise and PII. Set **`LLM_LOG_FULL=1`** (or `true`/`yes`) to log full prompts and responses; use only in development or debugging, as they may contain transcript content.

## 4. Language of analysis output (Czech)

The transcripts are typically in **Czech**. To keep all analysis text in Czech:

- **Phase 1 (topics):** Prompts already instruct the model to keep topic labels in the same language as the transcript (Czech).
- **Phase 2 (topic summaries):** The prompt explicitly requires the summary to be written in Czech so `topic_summaries[].summary` is in Czech.
- **Phase 3 (speaker contributions):** The prompt explicitly requires each speaker contribution summary to be written in Czech so `speaker_contributions[].summary` is in Czech.

Prompt templates are in `src/debate_analyzer/analysis/prompts.py`. Changing the language instruction there affects all future LLM runs.

## 5. Output schema

Each `_llm_analysis.json` file contains:

- **main_topics**: Each element has `id`, `title`, `description`, and **`keywords`** (list of strings) — terms derived from the topic title and description, used to find the relevant transcript excerpt (for debugging/inspection).

```json
{
  "main_topics": [
    { "id": "t1", "title": "short label", "description": "optional", "keywords": ["label", "short", ...] }
  ],
  "topic_summaries": [
    { "topic_id": "t1", "summary": "Discussion outcome for this topic." }
  ],
  "speaker_contributions": [
    { "topic_id": "t1", "speaker_id_in_transcript": "SPEAKER_06", "summary": "Position or contribution." }
  ]
}
```

## 6. Import into the web app

To attach analysis to a transcript in the DB (for the admin UI or API):

- **From S3:** `POST /api/admin/transcripts/{transcript_id}/analysis/import` with body:
  `{ "source_uri": "s3://bucket/key/<stem>_llm_analysis.json", "model_name": "Qwen/Qwen2-1.5B-Instruct", "source": "batch" }`
- **Inline:** Same endpoint with body:
  `{ "result": { "main_topics": [...], "topic_summaries": [...], "speaker_contributions": [...] }, "model_name": "...", "source": "api" }`

Get the latest analysis: `GET /api/admin/transcripts/{transcript_id}/analysis`.

## 7. Chunking and excerpts (long transcripts)

The job sets chunk and excerpt size from `LLM_MAX_MODEL_LEN` (default 8k) so the model never receives more context than it supports.

- **Phase 1 (topics):** The flattened transcript is split into overlapping chunks (within the context limit). The LLM extracts topics per chunk; topics are merged and deduplicated by title.
- **Phase 2 (summaries):** For each topic, a **topic-relevant excerpt** is built by finding lines that mention the topic (from its title/description) and taking a window around them, truncated to the context limit. If no match is found, the start of the transcript is used. That excerpt is used to generate the discussion summary.
- **Phase 3 (speaker contributions):** The same per-topic excerpt is used to summarize each speaker’s contribution for that topic.

Chunking is **required** when the transcript exceeds the configured context; the runner enforces it automatically.

## 8. Local / testing

- **Mock backend:** Run the batch module with `MOCK_LLM=1` and `TRANSCRIPT_S3_URI` or `TRANSCRIPTS_S3_PREFIX` pointing to a local file or directory (e.g. `file:///path/to/transcript.json`). No GPU or vLLM needed.
- **Analysis module:** The `debate_analyzer.analysis` package can be tested with `MockLLMBackend` in unit tests; see `tests/`.

## 9. Related

- **AWS Batch (transcribe, download, stats):** [DEPLOYMENT_AWS_BATCH.md](DEPLOYMENT_AWS_BATCH.md)
- **Terraform:** LLM job definition and ECR repo are in `deploy/terraform/` (job definition `debate-analyzer-job-llm-analysis`, ECR `debate-analyzer-llm`).

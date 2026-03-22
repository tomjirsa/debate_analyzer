# Run LLM analysis locally (Ollama, e.g. Llama)

**Prereqs:** `poetry install --extras llm` · Ollama running · model pulled (`ollama pull <name>` must match `OLLAMA_MODEL`)

**Single transcript** (filename must include `_transcription.json`):

```bash
TRANSCRIPT_S3_URI="/absolute/path/to/foo_transcription.json" \
OLLAMA_MODEL="llama3.2" \
poetry run python -m debate_analyzer.batch.llm_analysis_job
```

Writes `foo_llm_analysis.json` next to the transcript.

**Optional:** `scripts/run-llm-analysis-local.sh <path-to*_transcription.json> [OLLAMA_MODEL]` (from repo root; resolves repo via `git`).

**Paths:** Plain filesystem paths and `file:///absolute/path/...` both work. Prefer absolute paths if you hit odd resolution with `file://`.

**More detail:** `doc/LLM_ANALYSIS.md` (AWS Batch, import API, troubleshooting).

## Environment variables for local run


| Variable                        | Default                  | Role                                                                                                      |
| ------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------- |
| `TRANSCRIPT_S3_URI`             | —                        | One transcript (`s3://`, `file://`, or local path). Required unless using prefix.                         |
| `TRANSCRIPTS_S3_PREFIX`         | —                        | `s3://bucket/prefix/` — all `*_transcription.json` under prefix. Mutually exclusive with URI in practice. |
| `MOCK_LLM`                      | off                      | `1` / `true` / `yes` → mock backend (no Ollama).                                                          |
| `OLLAMA_HOST`                   | `http://localhost:11434` | Ollama HTTP API.                                                                                          |
| `OLLAMA_MODEL`                  | —                        | Model tag (e.g. `llama3.2`). If unset, falls back to `LLM_MODEL_ID`.                                      |
| `LLM_MODEL_ID`                  | `qwen2.5:7b`             | Used only if `OLLAMA_MODEL` is empty.                                                                     |
| `LLM_MAX_MODEL_LEN`             | `8192`                   | Passed to Ollama as `num_ctx` (min 1024 in backend). Also feeds chunk budget unless overridden below.     |
| `LLM_TEMPERATURE`               | `0.0`                    | Sampling temp; clamped to `[0, 2]`.                                                                       |
| `LLM_OLLAMA_MAX_CONTENT_TOKENS` | —                        | If set, max content tokens for Phase 1 / sizing (min 1000). Overrides `LLM_MAX_MODEL_LEN - 3500` reserve. |
| `LLM_PHASE1_MAX_CHUNK_TOKENS`   | `8000`                   | Cap on Phase 1 chunk size (min 1000 if set); combined with above via `min()`.                             |
| `LLM_OLLAMA_MAX_EXCERPT_TOKENS` | `3000`                   | Phase 2/3 excerpt cap (min 500 if set).                                                                   |
| `LLM_CHARS_PER_TOKEN`           | `4`                      | Char/token estimate for chunking (`src/debate_analyzer/analysis/chunking.py`). Try `3` for Czech.         |
| `LLM_MIN_SEGMENT_WORDS`         | `15`                     | Skip segments with fewer words.                                                                           |
| `LLM_LOG_FULL`                  | off                      | `1` / `true` / `yes` → full prompt/response logs (PII risk).                                              |


**Reserve:** Effective Phase 1 budget uses `3500` tokens reserved for template + reply unless `LLM_OLLAMA_MAX_CONTENT_TOKENS` is set (`src/debate_analyzer/batch/llm_analysis_job.py`).

**Logging (stderr):** Without `LLM_LOG_FULL`, requests truncate at 500 chars and responses at 1000.

## Llama 3.2 3B — maximum context

Llama 3.2 3B supports a large context window (e.g. 128K tokens in Ollama). To use the maximum **Phase 1** content budget, set both `LLM_MAX_MODEL_LEN` and `LLM_PHASE1_MAX_CHUNK_TOKENS`: the default Phase 1 chunk cap is **8000**, so raising only `LLM_MAX_MODEL_LEN` still leaves Phase 1 capped at 8000 until `LLM_PHASE1_MAX_CHUNK_TOKENS` is raised too.

Pull the model (tag must match `OLLAMA_MODEL`):

```bash
ollama pull llama3.2:3b
```

Start Ollama with a context length aligned to `LLM_MAX_MODEL_LEN` (see [Ollama process](#ollama-process-not-read-by-python) below). Example for 131072-token context:

```bash
OLLAMA_CONTEXT_LENGTH=131072 ollama serve
```

Run the job with max-context variables (optional `LLM_OLLAMA_MAX_CONTENT_TOKENS` mirrors `LLM_MAX_MODEL_LEN - 3500` and is redundant if omitted):

```bash
TRANSCRIPT_S3_URI="/absolute/path/to/foo_transcription.json" \
OLLAMA_MODEL="llama3.2:3b" \
LLM_MAX_MODEL_LEN=131072 \
LLM_PHASE1_MAX_CHUNK_TOKENS=131072 \
LLM_OLLAMA_MAX_CONTENT_TOKENS=127572 \
poetry run python -m debate_analyzer.batch.llm_analysis_job
```

**Memory:** 128K context uses a lot of RAM/VRAM. On constrained machines, lower `LLM_MAX_MODEL_LEN` and `LLM_PHASE1_MAX_CHUNK_TOKENS` together (keep them aligned with `OLLAMA_CONTEXT_LENGTH` when you start `ollama serve`).

## Ollama process (not read by Python)

If the server still uses a 2048 context, start Ollama with a matching context, e.g. `OLLAMA_CONTEXT_LENGTH=8192 ollama serve` (align with `LLM_MAX_MODEL_LEN`). `**OLLAMA_MODELS`** sets where Ollama stores weights (e.g. EFS on Batch); optional locally.

## After analysis

Import into the DB / webapp: [upload-local-data-to-db.md](../data-upload/upload-local-data-to-db.md) (use `import_llm_analysis` when you need analysis in the DB).
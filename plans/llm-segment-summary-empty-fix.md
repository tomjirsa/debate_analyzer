# Plan: Fix empty segment summaries in LLM analysis

## Context

Segment summaries in `*_llm_analysis.json` sometimes have `"summary": ""` and `"keywords": []` even when the source transcript block has substantial text. Example: segment `uid` `4b2981c1-025f-4947-a922-5bfccfb36024` in the Brno-Líšeň “26. zasedání” transcript (~108 words of Czech in `_transcription.json`, empty in `_llm_analysis.json`).

## What the data showed (sample meeting)

- **154** `segment_summaries` entries; **78** with empty `summary` (~50%).
- Empty segments are **not** shorter on average: median **152** words (empty) vs **46** words (non-empty).
- The example segment is above `LLM_MIN_SEGMENT_WORDS` (e.g. 15), so it was **not** skipped; the pipeline **wrote a row** but with **empty** summary/keywords after the LLM/parsing step.

## Root cause (primary)

Summaries are produced in `run_segment_summaries` → `_parse_summary_json()` in `src/debate_analyzer/analysis/segment_summary_runner.py`. That returns `("", [])` when:

- there is no parseable JSON object, or
- `json.loads` fails, or
- the `"summary"` key is missing or empty.

The Ollama backend (`src/debate_analyzer/analysis/backend_ollama.py`) builds `ChatOllama` with `num_ctx` but **does not set `num_predict`**. LangChain documents that when unset, Ollama’s effective generation cap is **small** (on the order of **128** tokens). The analysis code calls `generate_batch(..., max_tokens=2048)` (see `segment_summary_runner` / `run_analysis`), but **`generate()` ignores `max_tokens`** and does not forward it to Ollama.

**Effect:** Intended max output is **2048** tokens; the server often caps generation at **~128** tokens. If the model emits preamble, thinking, or a long Czech JSON string, the reply is **truncated** → incomplete or invalid JSON → parse failure → **empty** `summary`/`keywords`. This matches ~half of segments failing in a brittle way and longer turns being somewhat more exposed.

## Secondary contributors

1. **System prompt** (`SYSTEM_PROMPT_RESPONSE_LANGUAGE`) forces Czech everywhere. Some models may use Czech **keys** in JSON (e.g. `shrnutí` instead of `summary`); the parser only reads `data.get("summary")`, so the summary can appear empty even if text exists under another key.
2. **Brace-based JSON extraction** in `_parse_summary_json` can mis-fire on malformed output (less likely than truncation, but possible).
3. **Split-then-merge** for very long blocks: multiple chunk parse failures can compound; there is merge fallback logic for some cases, but single-call parse failure has no retry.

## Fix plan (ordered)

### 1. Wire generation budget to Ollama (must-do)

- Set `num_predict` on `ChatOllama` to match the analysis pipeline (e.g. **2048**, or an env var such as `LLM_MAX_TOKENS_PER_REPLY` aligned with `max_tokens_per_reply` in `run_analysis` / `run_segment_summaries`).
- Prefer **using the `max_tokens` argument** in `generate()` / `generate_batch()` and passing it through to `invoke` if LangChain supports per-call overrides; otherwise document that global `num_predict` matches the job’s `max_tokens_per_reply`.

**Files:** `src/debate_analyzer/analysis/backend_ollama.py`

### 2. Harden parsing (should-do)

- In `_parse_summary_json`, accept fallback keys for the summary string (e.g. **`shrnutí`** if `summary` is missing).
- Optionally strip markdown ```json``` fences before parsing.

**Files:** `src/debate_analyzer/analysis/segment_summary_runner.py`

### 3. Observability (should-do)

- When parse yields empty, log a **short warning** (and optionally the first N characters of the raw response) without enabling full `LLM_LOG_FULL`, to confirm truncation vs wrong keys.

**Files:** `segment_summary_runner.py` and/or `llm_analysis_job.py` logging helpers

### 4. Optional improvements

- Use Ollama **`format="json"`** for these calls if compatible with prompts and model.
- **Retry once** on empty parse with a minimal “reply with only JSON” follow-up.

### 5. Verification

- Re-run LLM analysis on the same transcript after (1); expect a **large drop** in empty summaries.
- Add or extend unit tests for `_parse_summary_json` (fallback keys, fenced JSON) and for Ollama backend `num_predict` wiring if testable.

## References (code)

- `src/debate_analyzer/analysis/segment_summary_runner.py` — `_parse_summary_json`, `run_segment_summaries`
- `src/debate_analyzer/analysis/backend_ollama.py` — `ChatOllama` construction, `generate` / `generate_batch`
- `src/debate_analyzer/analysis/runner.py` — `max_tokens_per_reply` passed into `run_segment_summaries`
- `src/debate_analyzer/batch/llm_analysis_job.py` — job env and `_run_one`

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

1. **System prompt** (`SYSTEM_PROMPT_RESPONSE_LANGUAGE`) forces Czech for *values*, but the JSON **schema** must stay English. Some models still emit Czech **keys** (e.g. `shrnutí` instead of `summary`). The fix is **not** to accept those keys silently: **require** `summary` and `keywords` and **fail** the parse when the model uses wrong keys (so issues are visible in logs rather than silent empties).
2. **Brace-based JSON extraction** in `_parse_summary_json` can mis-fire on malformed output (less likely than truncation, but possible).
3. **Split-then-merge** for very long blocks: multiple chunk parse failures can compound; there is merge fallback logic for some cases. The fix adds a **single JSON-only retry** after the first failed parse (see §4).

## Fix plan (ordered)

### 1. Wire generation budget to Ollama (must-do)

- Set `num_predict` on `ChatOllama` to match the analysis pipeline (e.g. **2048**, or an env var such as `LLM_MAX_TOKENS_PER_REPLY` aligned with `max_tokens_per_reply` in `run_analysis` / `run_segment_summaries`).
- Prefer **using the `max_tokens` argument** in `generate()` / `generate_batch()` and passing it through to `invoke` if LangChain supports per-call overrides; otherwise document that global `num_predict` matches the job’s `max_tokens_per_reply`.

**Files:** `src/debate_analyzer/analysis/backend_ollama.py`

### 2. Enforce JSON contract + strict keys (should-do)

- **Prompt:** State explicitly that the JSON object must use **only** the keys **`summary`** and **`keywords`** (English keys; Czech content inside strings is fine).
- **`_parse_summary_json`:** Do **not** map Czech keys (e.g. `shrnutí`) onto `summary`. If the parsed object has Czech keys but not `summary`/`keywords`, **fail** the parse the same as malformed JSON (empty result path used today, but distinguishable via logs below).
- Optionally strip markdown ```json``` fences before parsing (still required for valid extraction).

**Files:** `src/debate_analyzer/analysis/segment_summary_runner.py` (and any shared prompt constants)

### 3. Observability (should-do)

- **When JSON parsing fails** (`json.loads` error, no extractable object, or schema violation including wrong keys): log at **warning** (or **error** if you prefer) with a short reason and the **first N characters** of the raw model response (cap length; no need for `LLM_LOG_FULL`).
- When parse succeeds but `summary` is empty after enforcing the contract, log separately if useful (truncation vs empty string).
- Keep logs actionable: include failure class, e.g. `json_decode_error`, `missing_keys`, `wrong_keys_shrnuti`, `empty_summary`.

**Files:** `segment_summary_runner.py` and/or `llm_analysis_job.py` logging helpers

### 4. Ollama `format="json"` + single JSON-only retry (must-do)

- Enable Ollama **`format="json"`** for segment-summary generation calls (via `ChatOllama` / invoke options as supported by LangChain and the pinned Ollama client). Adjust prompts if needed so structured output still matches the required **`summary`** / **`keywords`** schema.
- After the **first** response, if `_parse_summary_json` fails or yields empty `summary`/`keywords` per contract, **retry exactly once** with a minimal follow-up instruction: output **only** valid JSON with keys `summary` and `keywords` (no prose, no markdown). Log the retry path (and first failure) for observability.

**Files:** `backend_ollama.py` (per-call or segment-runner-scoped `format`), `segment_summary_runner.py` (retry orchestration next to `run_segment_summaries` / batch generate).

### 5. Verification

- Re-run LLM analysis on the same transcript after (1); expect a **large drop** in empty summaries.
- Add or extend unit tests for `_parse_summary_json`: fenced JSON, **wrong keys** (`shrnutí` only → failed parse + no silent fill), **retry-once** behavior (mock: first fail → second success), and Ollama **`format="json"`** / `num_predict` wiring if mockable.
- Manually or in tests: confirm **logging fires** on deliberate malformed JSON / wrong-key payloads and on retry.

## References (code)

- `src/debate_analyzer/analysis/segment_summary_runner.py` — `_parse_summary_json`, `run_segment_summaries`
- `src/debate_analyzer/analysis/backend_ollama.py` — `ChatOllama` construction, `generate` / `generate_batch`
- `src/debate_analyzer/analysis/runner.py` — `max_tokens_per_reply` passed into `run_segment_summaries`
- `src/debate_analyzer/batch/llm_analysis_job.py` — job env and `_run_one`

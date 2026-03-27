---
name: segment-prompt-tuning
description: Iteratively tunes the Czech segment-summary LLM prompt using local Ollama, test transcription JSON, and optional baseline LLM analysis. Runs one-segment summaries, evaluates against a fixed rubric, revises a draft prompt template, and repeats until gates pass or max iterations; then advances to another segment. Use when tuning PROMPT_SEGMENT_SUMMARY, improving segment summaries, or when the user mentions segment prompt tuning, test_llm_analysis.json, or Ollama prompt experiments.
---

# Segment summary prompt tuning

## Purpose

Improve [`PROMPT_SEGMENT_SUMMARY`](../../../src/debate_analyzer/analysis/prompts.py) (and only if needed [`PROMPT_JSON_RETRY_PREFIX`](../../../src/debate_analyzer/analysis/prompts.py) or merge prompts) by running **single-segment** calls through the same stack as production (Ollama + JSON mode + parse/retry), using fixed test fixtures.

## Data sources (do not confuse them)

| File | Use |
|------|-----|
| [`data/test/test_transcription.json`](../../../data/test/test_transcription.json) | **Input text**: find the block where `uid` matches; use `text` (and metadata). |
| [`data/test/test_llm_analysis.json`](../../../data/test/test_llm_analysis.json) | **Optional baseline**: `segment_summaries[]` with the same `uid` — regression signal only, not gold. |

**Never** use the analysis JSON as the model input; it does not contain the full segment transcript text.

## Prerequisites

- `poetry install --extras llm`
- Ollama running; model pulled (`OLLAMA_MODEL` or default)
- Context length: start Ollama with `OLLAMA_CONTEXT_LENGTH` aligned to `LLM_MAX_MODEL_LEN` if you see truncation (see [reference.md](reference.md))

## Workflow

1. Pick a segment `uid` (see [reference.md](reference.md) for ordering ideas).
2. Load **segment text** from `test_transcription.json` by `uid`.
3. Edit the **draft** template [`segment_summary_prompt_draft.txt`](segment_summary_prompt_draft.txt) (must contain `{text}` where the segment body goes). Do not edit [`prompts.py`](../../../src/debate_analyzer/analysis/prompts.py) on every iteration—only after the draft passes the rubric for that segment.
4. Run the helper script (from repo root):

   ```bash
   poetry run python .cursor/skills/segment-prompt-tuning/scripts/run_segment_summary.py \
     --transcription data/test/test_transcription.json \
     --uid "<uid>" \
     --prompt-file .cursor/skills/segment-prompt-tuning/segment_summary_prompt_draft.txt
   ```

   Optional comparison to baseline:

   ```bash
   poetry run python .cursor/skills/segment-prompt-tuning/scripts/run_segment_summary.py \
     --transcription data/test/test_transcription.json \
     --uid "<uid>" \
     --prompt-file .cursor/skills/segment-prompt-tuning/segment_summary_prompt_draft.txt \
     --baseline data/test/test_llm_analysis.json
   ```

5. **Evaluate** using the rubric below (structured; do not use vague “looks fine”).
6. If any gate fails: revise the draft and go to step 4. **Max 5 iterations per segment** unless the user says otherwise; if still failing, document and move on or stop.
7. If all gates pass: optionally append a line to [`tuning-log.md`](tuning-log.md), pick **another** `uid` (e.g. stratify short vs long segments), and repeat from step 2.
8. When satisfied across segments: apply **one** patch to [`src/debate_analyzer/analysis/prompts.py`](../../../src/debate_analyzer/analysis/prompts.py) copying the final draft into `PROMPT_SEGMENT_SUMMARY`, sync [`segment_summary_prompt_draft.txt`](segment_summary_prompt_draft.txt) or leave it as a copy of production.
9. Run `make test` (and spot-check Ollama on 1–2 uids if possible).

## Evaluation rubric (all must pass for “good”)

**JSON / schema**

- Parser returns non-empty `summary` and `keywords` (same rules as production).
- Empty summary = fail.

**Language**

- Summary is Czech; flag stray English words or mixed-language artifacts (e.g. “could”, “possibility” when the transcript is Czech).

**Faithfulness**

- Claims in the summary must be supported by the segment text; flag clear hallucinations or wrong entities.

**Keywords**

- Prefer 3–8 keywords; list format; align with content; no obvious duplicates.

**Baseline (optional)**

- If `--baseline` was used: note whether the new output fixes known issues vs the stored summary; baseline may be wrong—do not treat it as ground truth.

## Implementation notes

- The script uses [`run_single_segment_summary`](../../../src/debate_analyzer/analysis/segment_summary_runner.py) and [`get_ollama_backend`](../../../src/debate_analyzer/analysis/backend_ollama.py) with [`SYSTEM_PROMPT_RESPONSE_LANGUAGE`](../../../src/debate_analyzer/analysis/prompts.py)—same path as the full pipeline.
- Do not reimplement JSON extraction; rely on the module.
- This skill does **not** run grid search or automated hyperparameter optimization—the agent applies judgment using the rubric.

## Final merge checklist

- [ ] Draft content merged into `PROMPT_SEGMENT_SUMMARY` in `prompts.py`
- [ ] `make test` passes
- [ ] Optional: Ollama spot-check on at least one uid

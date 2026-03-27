# Segment prompt tuning — reference

**Production templates:** LLM analysis loads

- [`segment_summary_prompt.txt`](../../src/debate_analyzer/analysis/segment_summary_prompt.txt) → `PROMPT_SEGMENT_SUMMARY`
- [`merge_summaries_prompt.txt`](../../src/debate_analyzer/analysis/merge_summaries_prompt.txt) → `PROMPT_MERGE_SUMMARIES` (split-then-merge, per-speaker merge, transcript merge)

Keep [`segment_summary_prompt_draft.txt`](segment_summary_prompt_draft.txt) and [`merge_summaries_prompt_draft.txt`](merge_summaries_prompt_draft.txt) in sync with the files above when copying tuning results into production.

## Environment variables

| Variable | Role |
|----------|------|
| `OLLAMA_HOST` | Ollama HTTP API (default `http://localhost:11434`). |
| `OLLAMA_MODEL` | Model name (fallback: `LLM_MODEL_ID`, then `qwen2.5:7b`). |
| `LLM_MAX_MODEL_LEN` | Context window hint for the client (default `8192`). |
| `LLM_TEMPERATURE` | Float `0.0`–`2.0` (default `0.0`). |
| `OLLAMA_CONTEXT_LENGTH` | **Server-side**: set when **starting** `ollama serve` so the daemon’s context matches your job (e.g. `65535`). If the server truncates at 2048, summaries may degrade. |

Full local run notes: [local-ollama-run.md](../local-development/references/llm-analysis/local-ollama-run.md).

## Example commands

Prerequisites: `poetry install --extras llm`, Ollama running, model pulled.

Single segment (draft prompt file):

```bash
cd /path/to/debate_analyzer
poetry run python .cursor/skills/segment-prompt-tuning/scripts/run_segment_summary.py \
  --transcription data/test/test_transcription.json \
  --uid "b04e88d7-1031-4df4-9f39-b756db4485a0" \
  --prompt-file .cursor/skills/segment-prompt-tuning/segment_summary_prompt_draft.txt
```

With baseline comparison:

```bash
poetry run python .cursor/skills/segment-prompt-tuning/scripts/run_segment_summary.py \
  --transcription data/test/test_transcription.json \
  --uid "5ec20f1f-1fc0-40f9-9e14-399c10a3e09f" \
  --prompt-file .cursor/skills/segment-prompt-tuning/segment_summary_prompt_draft.txt \
  --baseline data/test/test_llm_analysis.json
```

Optional: `--max-tokens 2048` to override reply length.

## Merge summaries (partial → one JSON)

Partials are **not** raw transcript text; they are `(summary, keywords)` tuples, same as after segment summarization. Use consecutive rows from [`data/test/test_llm_analysis.json`](../../data/test/test_llm_analysis.json) `segment_summaries` to simulate merging chunk partials or multiple blocks.

```bash
poetry run python .cursor/skills/segment-prompt-tuning/scripts/run_merge_summaries.py \
  --analysis data/test/test_llm_analysis.json \
  --start 0 --count 3 \
  --prompt-file .cursor/skills/segment-prompt-tuning/merge_summaries_prompt_draft.txt
```

Evaluate with the same JSON/language/faithfulness/keywords rubric as segment summaries; inputs are summaries, so faithfulness means **do not invent content beyond what the partials state**.

## Suggested segment ordering

- **Stratify**: mix short blocks (e.g. under 100 words) and long monologues.
- **Known issues**: segments whose baseline in `test_llm_analysis.json` shows English artifacts or hallucinations are good stress tests (e.g. uids with mixed “could” / “possibility” in older summaries).
- **Sequential**: walk `segment_summaries` in file order if you want coverage without thinking about stratification.

## Iteration limits

- Default **5 iterations per segment** in the skill workflow; stop early when the rubric passes.
- If still failing after 5: document in `tuning-log.md` and skip or ask the user.

## Rubric (short)

1. Valid JSON with non-empty Czech `summary` and sensible `keywords` (3–8).
2. No unsupported claims vs segment text.
3. Czech only in the summary (no stray English).
4. Baseline file optional — not authoritative.

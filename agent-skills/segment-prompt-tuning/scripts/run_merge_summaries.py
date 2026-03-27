#!/usr/bin/env python3
"""Run one merge-summary call via Ollama (same JSON path as production).

Uses partial summaries from ``data/test/test_llm_analysis.json`` (or any analysis
JSON with ``segment_summaries``) to simulate chunk merge / speaker merge.

Example (from repo root):

  poetry run python .cursor/skills/segment-prompt-tuning/scripts/run_merge_summaries.py \\
    --analysis data/test/test_llm_analysis.json \\
    --start 0 --count 3 \\
    --prompt-file .cursor/skills/segment-prompt-tuning/merge_summaries_prompt_draft.txt
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_partials(
    analysis_path: Path,
    *,
    start: int,
    count: int,
) -> list[tuple[str, list[str]]]:
    """Build ``(summary, keywords)`` tuples from consecutive ``segment_summaries``."""
    data = json.loads(analysis_path.read_text(encoding="utf-8"))
    blocks = data.get("segment_summaries") or []
    if start < 0 or count < 1:
        raise SystemExit("--start must be >= 0 and --count >= 1")
    if start + count > len(blocks):
        raise SystemExit(
            f"Need segment_summaries[{start}:{start + count}] but only "
            f"{len(blocks)} entries in {analysis_path}"
        )
    out: list[tuple[str, list[str]]] = []
    for block in blocks[start : start + count]:
        summary = str(block.get("summary") or "").strip()
        kw_raw = block.get("keywords")
        keywords: list[str] = []
        if isinstance(kw_raw, list):
            keywords = [str(x).strip() for x in kw_raw if str(x).strip()]
        out.append((summary, keywords))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge N consecutive segment summaries from analysis JSON (Ollama)."
    )
    parser.add_argument(
        "--analysis",
        type=Path,
        required=True,
        help="Path to *_llm_analysis.json with segment_summaries",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Index in segment_summaries (0-based, default 0)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=2,
        help="How many consecutive segments to merge (default 2)",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        required=True,
        help="Merge template; must include {partials} placeholder",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Max tokens per reply (default 2048)",
    )
    args = parser.parse_args()

    partials = _load_partials(args.analysis, start=args.start, count=args.count)

    template = args.prompt_file.read_text(encoding="utf-8")
    if "{partials}" not in template:
        raise SystemExit("Prompt template must contain {partials} placeholder")

    from debate_analyzer.analysis.prompts import (
        SYSTEM_PROMPT_RESPONSE_LANGUAGE,
        format_merge_partials_block,
    )
    from debate_analyzer.analysis.segment_summary_runner import (
        run_single_segment_summary,
    )
    from debate_analyzer.analysis.backend_ollama import get_ollama_backend

    prompt = template.format(partials=format_merge_partials_block(partials))

    backend = get_ollama_backend(system_prompt=SYSTEM_PROMPT_RESPONSE_LANGUAGE)

    def generate_batch(
        prompts: list[str],
        max_tokens: int = 2048,
        *,
        json_mode: bool = False,
    ) -> list[str]:
        return [
            backend.generate(p, max_tokens=max_tokens, json_mode=json_mode)
            for p in prompts
        ]

    summary, keywords, raw = run_single_segment_summary(
        prompt,
        generate_batch,
        max_tokens_per_reply=args.max_tokens,
        log_context=f"merge_cli start={args.start} count={args.count}",
    )

    out = {
        "source": {
            "analysis": str(args.analysis),
            "start": args.start,
            "count": args.count,
        },
        "summary": summary,
        "keywords": keywords,
        "raw_model": raw,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if not summary:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

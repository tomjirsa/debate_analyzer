#!/usr/bin/env python3
"""Run one segment summary via Ollama using the same JSON path as production.

Invoke from the repository root, e.g.:

  poetry run python .cursor/skills/segment-prompt-tuning/scripts/run_segment_summary.py \\
    --transcription data/test/test_transcription.json \\
    --uid "<uuid>" \\
    --prompt-file .cursor/skills/segment-prompt-tuning/segment_summary_prompt_draft.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_transcription_block(transcription_path: Path, uid: str) -> dict[str, object]:
    """Return the transcription block matching ``uid``."""
    data = json.loads(transcription_path.read_text(encoding="utf-8"))
    blocks = data.get("transcription") or []
    for block in blocks:
        if str(block.get("uid", "")) == uid:
            return block
    raise SystemExit(f"No block with uid={uid!r} in {transcription_path}")


def _baseline_for_uid(baseline_path: Path, uid: str) -> dict[str, object] | None:
    """Return segment_summaries entry for ``uid``, or None."""
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    for seg in data.get("segment_summaries") or []:
        if str(seg.get("uid", "")) == uid:
            return seg
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run segment summary for one uid with a prompt template ({text})."
    )
    parser.add_argument(
        "--transcription",
        type=Path,
        required=True,
        help="Path to *_transcription.json",
    )
    parser.add_argument("--uid", required=True, help="Segment uid to summarize")
    parser.add_argument(
        "--prompt-file",
        type=Path,
        required=True,
        help="Prompt template file; must include {text} placeholder",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Optional *_llm_analysis.json for side-by-side baseline summary",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Max tokens per reply (default 2048)",
    )
    args = parser.parse_args()

    block = _load_transcription_block(args.transcription, args.uid)
    text = str(block.get("text") or "").strip()
    if not text:
        raise SystemExit("Segment text is empty")

    template = args.prompt_file.read_text(encoding="utf-8")
    if "{text}" not in template:
        raise SystemExit("Prompt template must contain {text} placeholder")

    prompt = template.format(text=text)

    from debate_analyzer.analysis.backend_ollama import get_ollama_backend
    from debate_analyzer.analysis.prompts import SYSTEM_PROMPT_RESPONSE_LANGUAGE
    from debate_analyzer.analysis.segment_summary_runner import (
        run_single_segment_summary,
    )

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
        log_context=f"cli uid={args.uid[:8]}",
    )

    out = {
        "uid": args.uid,
        "speaker": block.get("speaker"),
        "start": block.get("start"),
        "end": block.get("end"),
        "summary": summary,
        "keywords": keywords,
        "raw_model": raw,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if args.baseline:
        base = _baseline_for_uid(args.baseline, args.uid)
        if base:
            print(
                "\n--- baseline (reference only) ---\n",
                file=sys.stderr,
            )
            print(
                json.dumps(
                    {
                        "summary": base.get("summary"),
                        "keywords": base.get("keywords"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
        else:
            print(
                f"No segment_summaries entry for uid in {args.baseline}",
                file=sys.stderr,
            )

    if not summary:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

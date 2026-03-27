#!/usr/bin/env python3
"""Sequential segment experiment: one uid at a time; tighten prompt on failed checks.

Run from repository root:

  LLM_MAX_MODEL_LEN=65536 poetry run python \\
    agent-skills/segment-prompt-tuning/scripts/sequential_tune_experiment.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DRAFT = (
    _REPO_ROOT / "agent-skills/segment-prompt-tuning/segment_summary_prompt_draft.txt"
)
_RUNNER = (
    _REPO_ROOT / "agent-skills/segment-prompt-tuning/scripts/run_segment_summary.py"
)
_TRANSCRIPTION = _REPO_ROOT / "data/test/test_transcription.json"
_ANALYSIS = _REPO_ROOT / "data/test/test_llm_analysis.json"

_ENGLISH = re.compile(
    r"\b(the|and|for|not|but|could|would|should|possibility|suggest|Suggest)\b",
    re.IGNORECASE,
)

_STRENGTHENERS: tuple[str, ...] = (
    " Use only names, surnames, and roles exactly as spoken in the segment; "
    "do not invent job titles or institutional roles (e.g. do not introduce "
    "words like poslanec or smluvní unless they appear verbatim in the segment).",
    " The summary must be grammatical Czech from the first word; avoid "
    "nonsensical collocations, fused nonsense words, or garbled openings.",
    " For short or procedural segments, keep the summary short and literal; "
    "describe only what the speaker actually does (e.g. navrhuje hlasování) "
    "without inventing who they are.",
)


def _load_uids() -> list[str]:
    data = json.loads(_ANALYSIS.read_text(encoding="utf-8"))
    return [str(s["uid"]) for s in data.get("segment_summaries") or []]


def _evaluate(summary: str, keywords: list[str]) -> tuple[bool, str]:
    if not (summary or "").strip():
        return False, "empty_summary"
    if _ENGLISH.search(summary):
        return False, "english_in_summary"
    if not (3 <= len(keywords) <= 8):
        return False, f"keywords_count_{len(keywords)}"
    return True, "ok"


def _run_one(uid: str, prompt_text: str, tmp_path: Path) -> tuple[str, list[str]]:
    tmp_path.write_text(prompt_text, encoding="utf-8")
    env = {
        **os.environ,
        "LLM_MAX_MODEL_LEN": os.environ.get("LLM_MAX_MODEL_LEN", "65536"),
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(_RUNNER),
            "--transcription",
            str(_TRANSCRIPTION),
            "--uid",
            uid,
            "--prompt-file",
            str(tmp_path),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or "") + (proc.stdout or "")
        raise RuntimeError(msg.strip() or "run_segment_summary failed")
    data = json.loads(proc.stdout.strip())
    return str(data.get("summary") or ""), list(data.get("keywords") or [])


def main() -> None:
    uids = _load_uids()
    base = _DRAFT.read_text(encoding="utf-8")
    if "{text}" not in base:
        raise SystemExit("Draft must contain {text}")

    extra = ""
    strengthener_idx = 0
    log_lines: list[str] = []

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
        dir=str(_REPO_ROOT / "agent-skills/segment-prompt-tuning"),
    ) as tf:
        tmp_path = Path(tf.name)

    try:
        for i, uid in enumerate(uids, start=1):
            short = uid[:8]
            for run_idx in range(5):
                prompt_text = base + extra
                try:
                    summary, keywords = _run_one(uid, prompt_text, tmp_path)
                except Exception as e:
                    log_lines.append(f"{i:2d} {short}… FAIL run_error {e!s}")
                    break
                ok, reason = _evaluate(summary, keywords)
                if ok:
                    log_lines.append(
                        f"{i:2d} {short}… pass  kw={len(keywords)}  "
                        f"runs={run_idx + 1}"
                    )
                    break
                if run_idx == 4:
                    log_lines.append(f"{i:2d} {short}… fail  {reason}  after 5 runs")
                    break
                if strengthener_idx >= len(_STRENGTHENERS):
                    log_lines.append(
                        f"{i:2d} {short}… fail  {reason}  (no strengtheners left)"
                    )
                    break
                extra += _STRENGTHENERS[strengthener_idx]
                strengthener_idx += 1
                log_lines.append(
                    f"{i:2d} {short}… retry {reason}  "
                    f"-> strengthener #{strengthener_idx}"
                )
    finally:
        tmp_path.unlink(missing_ok=True)

    final_prompt = base + extra
    _DRAFT.write_text(final_prompt, encoding="utf-8")

    print("=== per-segment log ===")
    for line in log_lines:
        print(line)
    print()
    print("=== final prompt (saved to segment_summary_prompt_draft.txt) ===")
    print(final_prompt)


if __name__ == "__main__":
    main()

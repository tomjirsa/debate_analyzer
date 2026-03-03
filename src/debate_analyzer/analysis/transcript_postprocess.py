"""LLM post-processing of transcript segments: grammar and ASR error correction only."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from debate_analyzer.analysis.prompts import build_correct_segment_prompt


def run_correction(
    payload: dict[str, Any],
    generate_batch: Callable[[list[str], int], list[str]],
    max_tokens_per_reply: int = 1024,
    postprocess_model_label: str = "ollama",
) -> dict[str, Any]:
    """
    Correct grammar and obvious transcription errors in transcript segments via LLM.

    Preserves start, end, speaker, confidence; only replaces segment "text".
    On empty or invalid LLM response, keeps original text. Adds model.postprocess
    for traceability.

    Args:
        payload: Transcript dict with "transcription" list of segment dicts
            (each with "text", "start", "end", "speaker", optionally "confidence").
        generate_batch: (prompts, max_tokens) -> list of responses, same order.
        max_tokens_per_reply: Max tokens per segment reply (default 1024).
        postprocess_model_label: Label for model.postprocess in output (e.g. "ollama").

    Returns:
        New dict with same structure; transcription[].text updated; model dict
        gets model["postprocess"] = postprocess_model_label.
    """
    transcription = payload.get("transcription") or []
    if not transcription:
        result = dict(payload)
        if "model" in result and isinstance(result["model"], dict):
            result["model"] = dict(result["model"])
            result["model"]["postprocess"] = postprocess_model_label
        else:
            result["model"] = {"postprocess": postprocess_model_label}
        return result

    prompts = [
        build_correct_segment_prompt(seg.get("text", "") or "") for seg in transcription
    ]
    responses = generate_batch(prompts, max_tokens_per_reply)

    corrected_segments: list[dict[str, Any]] = []
    for i, seg in enumerate(transcription):
        new_seg = dict(seg)
        raw = responses[i].strip() if i < len(responses) else ""
        if raw:
            new_seg["text"] = raw
        corrected_segments.append(new_seg)

    result = dict(payload)
    result["transcription"] = corrected_segments
    if "model" in result and isinstance(result["model"], dict):
        result["model"] = dict(result["model"])
        result["model"]["postprocess"] = postprocess_model_label
    else:
        result["model"] = {"postprocess": postprocess_model_label}
    return result

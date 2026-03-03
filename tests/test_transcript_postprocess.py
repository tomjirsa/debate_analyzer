"""Tests for transcript post-processing (grammar/ASR correction)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from debate_analyzer.analysis.backend import MockLLMBackend
from debate_analyzer.analysis.transcript_postprocess import run_correction


def test_run_correction_empty_payload() -> None:
    """Empty transcription yields payload with model.postprocess only."""
    payload = {"video_path": "/x", "transcription": []}

    def no_calls(_prompts: list[str], _max: int) -> list[str]:
        return []

    result = run_correction(payload, no_calls, postprocess_model_label="test")
    assert result["transcription"] == []
    assert result["model"]["postprocess"] == "test"
    assert result["video_path"] == "/x"


def test_run_correction_preserves_structure_and_model() -> None:
    """run_correction preserves start, end, speaker, confidence; adds postprocess."""
    payload = {
        "video_path": "/a",
        "duration": 100.0,
        "model": {"whisper": "medium", "diarization": "pyannote"},
        "transcription": [
            {
                "start": 0.0,
                "end": 5.0,
                "text": "Ahoj světe.",
                "speaker": "SPEAKER_00",
                "confidence": 0.9,
            },
        ],
    }

    def echo(prompts: list[str], _max: int) -> list[str]:
        # Return segment text from prompt (between first --- and second ---).
        out = []
        for p in prompts:
            parts = p.split("---")
            out.append(parts[1].strip() if len(parts) >= 2 else "")
        return out

    result = run_correction(payload, echo, postprocess_model_label="echo")
    assert len(result["transcription"]) == 1
    seg = result["transcription"][0]
    assert seg["start"] == 0.0
    assert seg["end"] == 5.0
    assert seg["speaker"] == "SPEAKER_00"
    assert seg["confidence"] == 0.9
    assert seg["text"] == "Ahoj světe."
    assert result["model"]["whisper"] == "medium"
    assert result["model"]["diarization"] == "pyannote"
    assert result["model"]["postprocess"] == "echo"


def test_run_correction_mock_backend_returns_unchanged_text() -> None:
    """With MockLLMBackend (correction prompt), segment text is returned unchanged."""
    payload = {
        "transcription": [
            {
                "start": 0.0,
                "end": 2.0,
                "text": "Chyba pravopisu.",
                "speaker": "SPEAKER_00",
            },
        ],
    }
    backend = MockLLMBackend()
    result = run_correction(
        payload,
        backend.generate_batch,
        max_tokens_per_reply=512,
        postprocess_model_label="mock",
    )
    assert result["transcription"][0]["text"] == "Chyba pravopisu."
    assert result["model"]["postprocess"] == "mock"
    assert backend.call_count == 1


def test_run_correction_fallback_empty_response() -> None:
    """When LLM returns empty string, original text is kept."""
    payload = {
        "transcription": [
            {"start": 0.0, "end": 1.0, "text": "Keep me.", "speaker": "SPEAKER_00"},
        ],
    }

    def empty_responses(_prompts: list[str], _max: int) -> list[str]:
        return [""]

    result = run_correction(payload, empty_responses, postprocess_model_label="test")
    assert result["transcription"][0]["text"] == "Keep me."


def test_run_correction_multiple_segments() -> None:
    """Multiple segments get one prompt each; order preserved."""
    payload = {
        "transcription": [
            {"start": 0.0, "end": 1.0, "text": "First.", "speaker": "SPEAKER_00"},
            {"start": 1.0, "end": 2.0, "text": "Second.", "speaker": "SPEAKER_01"},
        ],
    }
    backend = MockLLMBackend()
    result = run_correction(
        payload, backend.generate_batch, postprocess_model_label="mock"
    )
    assert len(result["transcription"]) == 2
    assert result["transcription"][0]["text"] == "First."
    assert result["transcription"][1]["text"] == "Second."
    assert backend.call_count == 2


def test_postprocess_job_run_one_local(tmp_path: Path) -> None:
    """Batch job reads _transcription_raw.json, writes _transcription.json (MOCK_LLM)."""
    raw_path = tmp_path / "debate_transcription_raw.json"
    payload = {
        "video_path": "/x",
        "transcription": [
            {"start": 0, "end": 1, "text": "Test.", "speaker": "SPEAKER_00"}
        ],
    }
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    os.environ["MOCK_LLM"] = "1"
    os.environ["TRANSCRIPT_S3_URI"] = str(raw_path)
    try:
        from debate_analyzer.batch import transcript_postprocess_job

        n = transcript_postprocess_job.run(str(raw_path))
        assert n == 1
        out_path = tmp_path / "debate_transcription.json"
        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["transcription"][0]["text"] == "Test."
        assert data["model"]["postprocess"] == "mock"
    finally:
        os.environ.pop("MOCK_LLM", None)
        os.environ.pop("TRANSCRIPT_S3_URI", None)

"""Tests for the batch stats job (per-speaker stats computation)."""


from debate_analyzer.batch.stats_job import _compute_speaker_stats


def test_compute_speaker_stats_empty():
    """Empty transcription yields empty list."""
    assert _compute_speaker_stats([]) == []


def test_compute_speaker_stats_single_speaker():
    """Single speaker aggregates total_seconds, segment_count, word_count."""
    transcription = [
        {"start": 0, "end": 3, "text": "one two three", "speaker": "SPEAKER_00"},
        {"start": 3, "end": 6, "text": "four five", "speaker": "SPEAKER_00"},
    ]
    rows = _compute_speaker_stats(transcription)
    assert len(rows) == 1
    assert rows[0]["speaker_id_in_transcript"] == "SPEAKER_00"
    assert rows[0]["total_seconds"] == 6.0
    assert rows[0]["segment_count"] == 2
    assert rows[0]["word_count"] == 5


def test_compute_speaker_stats_two_speakers():
    """Two speakers get separate rows."""
    transcription = [
        {"start": 0, "end": 2, "text": "hi", "speaker": "SPEAKER_00"},
        {"start": 2, "end": 5, "text": "hello world", "speaker": "SPEAKER_01"},
    ]
    rows = _compute_speaker_stats(transcription)
    assert len(rows) == 2
    by_speaker = {r["speaker_id_in_transcript"]: r for r in rows}
    assert by_speaker["SPEAKER_00"]["total_seconds"] == 2.0
    assert by_speaker["SPEAKER_00"]["word_count"] == 1
    assert by_speaker["SPEAKER_01"]["total_seconds"] == 3.0
    assert by_speaker["SPEAKER_01"]["word_count"] == 2


def test_compute_speaker_stats_missing_speaker_uses_unknown():
    """Segment without speaker key is treated as SPEAKER_UNKNOWN."""
    transcription = [{"start": 0, "end": 1, "text": "x", "speaker": None}]
    rows = _compute_speaker_stats(transcription)
    assert len(rows) == 1
    assert rows[0]["speaker_id_in_transcript"] == "SPEAKER_UNKNOWN"

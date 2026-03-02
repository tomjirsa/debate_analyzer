"""Tests for segment aggregator."""

import pytest

from debate_analyzer.transcriber.aggregator import aggregate_segments
from debate_analyzer.transcriber.models import TranscriptWithSpeaker


class TestAggregateSegments:
    """Tests for aggregate_segments."""

    def test_empty_input_returns_empty_list(self) -> None:
        """Empty input returns empty list."""
        result = aggregate_segments([], max_segment_duration_sec=60.0)
        assert result == []

    def test_single_segment_unchanged(self) -> None:
        """Single segment is returned unchanged."""
        seg = TranscriptWithSpeaker(
            start=10.0,
            end=25.0,
            text="Hello world",
            speaker="SPEAKER_00",
            confidence=0.9,
        )
        result = aggregate_segments([seg], max_segment_duration_sec=60.0)
        assert len(result) == 1
        assert result[0].start == 10.0
        assert result[0].end == 25.0
        assert result[0].text == "Hello world"
        assert result[0].speaker == "SPEAKER_00"
        assert result[0].confidence == 0.9

    def test_two_consecutive_same_speaker_merged_under_cap(self) -> None:
        """Two consecutive same-speaker segments under cap merge into one."""
        segments = [
            TranscriptWithSpeaker(0.0, 30.0, "Hello", "SPEAKER_00", 0.8),
            TranscriptWithSpeaker(30.0, 50.0, "world", "SPEAKER_00", 0.9),
        ]
        result = aggregate_segments(segments, max_segment_duration_sec=60.0)
        assert len(result) == 1
        assert result[0].start == 0.0
        assert result[0].end == 50.0
        assert result[0].text == "Hello world"
        assert result[0].speaker == "SPEAKER_00"
        assert result[0].confidence == pytest.approx(0.85)

    def test_same_speaker_over_cap_splits_when_adding_would_exceed(self) -> None:
        """When adding next segment would exceed max, current run is emitted; later segments can still merge."""
        segments = [
            TranscriptWithSpeaker(0.0, 40.0, "First", "SPEAKER_00", 1.0),
            TranscriptWithSpeaker(40.0, 80.0, "Second", "SPEAKER_00", 1.0),
            TranscriptWithSpeaker(80.0, 100.0, "Third", "SPEAKER_00", 1.0),
        ]
        result = aggregate_segments(segments, max_segment_duration_sec=60.0)
        # 0-40 (40s) emitted; 40-80 + 80-100 = 60s <= 60, so one merged segment 40-100
        assert len(result) == 2
        assert result[0].start == 0.0 and result[0].end == 40.0
        assert result[0].text == "First"
        assert result[1].start == 40.0 and result[1].end == 100.0
        assert result[1].text == "Second Third"

    def test_speaker_change_never_merged(self) -> None:
        """Segments from different speakers are never merged."""
        segments = [
            TranscriptWithSpeaker(0.0, 20.0, "First", "SPEAKER_00", 1.0),
            TranscriptWithSpeaker(20.0, 40.0, "Second", "SPEAKER_01", 1.0),
        ]
        result = aggregate_segments(segments, max_segment_duration_sec=60.0)
        assert len(result) == 2
        assert result[0].speaker == "SPEAKER_00" and result[0].text == "First"
        assert result[1].speaker == "SPEAKER_01" and result[1].text == "Second"

    def test_no_cap_when_max_duration_zero_merges_all_same_speaker(self) -> None:
        """When max_segment_duration_sec <= 0, same-speaker segments merge without cap."""
        segments = [
            TranscriptWithSpeaker(0.0, 40.0, "A", "SPEAKER_00", 0.8),
            TranscriptWithSpeaker(40.0, 80.0, "B", "SPEAKER_00", 0.9),
            TranscriptWithSpeaker(80.0, 120.0, "C", "SPEAKER_00", 1.0),
        ]
        result = aggregate_segments(segments, max_segment_duration_sec=0.0)
        assert len(result) == 1
        assert result[0].start == 0.0 and result[0].end == 120.0
        assert result[0].text == "A B C"
        assert result[0].confidence == pytest.approx(0.9)

    def test_negative_max_duration_no_cap(self) -> None:
        """Negative max_segment_duration_sec is treated as no cap."""
        segments = [
            TranscriptWithSpeaker(0.0, 50.0, "One", "SPEAKER_00", 1.0),
            TranscriptWithSpeaker(50.0, 100.0, "Two", "SPEAKER_00", 1.0),
        ]
        result = aggregate_segments(segments, max_segment_duration_sec=-1.0)
        assert len(result) == 1
        assert result[0].end == 100.0
        assert result[0].text == "One Two"

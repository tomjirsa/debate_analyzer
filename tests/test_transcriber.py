"""Tests for transcriber module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from debate_analyzer.transcriber.audio_extractor import (
    AudioExtractor,
    AudioExtractionError,
)
from debate_analyzer.transcriber.merger import TranscriptMerger
from debate_analyzer.transcriber.models import (
    SpeakerSegment,
    TranscriptSegment,
    TranscriptWithSpeaker,
)


class TestTranscriptSegment:
    """Tests for TranscriptSegment model."""

    def test_create_segment(self) -> None:
        """Test creating a transcript segment."""
        segment = TranscriptSegment(start=0.0, end=5.0, text="Hello world")

        assert segment.start == 0.0
        assert segment.end == 5.0
        assert segment.text == "Hello world"

    def test_to_dict(self) -> None:
        """Test converting segment to dictionary."""
        segment = TranscriptSegment(start=1.5, end=3.2, text="Test text")
        data = segment.to_dict()

        assert data == {"start": 1.5, "end": 3.2, "text": "Test text"}


class TestSpeakerSegment:
    """Tests for SpeakerSegment model."""

    def test_create_segment(self) -> None:
        """Test creating a speaker segment."""
        segment = SpeakerSegment(start=0.0, end=5.0, speaker_id="SPEAKER_00")

        assert segment.start == 0.0
        assert segment.end == 5.0
        assert segment.speaker_id == "SPEAKER_00"

    def test_to_dict(self) -> None:
        """Test converting segment to dictionary."""
        segment = SpeakerSegment(start=2.0, end=4.5, speaker_id="SPEAKER_01")
        data = segment.to_dict()

        assert data == {"start": 2.0, "end": 4.5, "speaker_id": "SPEAKER_01"}


class TestTranscriptWithSpeaker:
    """Tests for TranscriptWithSpeaker model."""

    def test_create_segment(self) -> None:
        """Test creating a merged segment."""
        segment = TranscriptWithSpeaker(
            start=0.0,
            end=5.0,
            text="Hello",
            speaker="SPEAKER_00",
            confidence=0.95,
        )

        assert segment.start == 0.0
        assert segment.end == 5.0
        assert segment.text == "Hello"
        assert segment.speaker == "SPEAKER_00"
        assert segment.confidence == 0.95

    def test_default_confidence(self) -> None:
        """Test default confidence value."""
        segment = TranscriptWithSpeaker(
            start=0.0,
            end=5.0,
            text="Hello",
            speaker="SPEAKER_00",
        )

        assert segment.confidence == 1.0


class TestAudioExtractor:
    """Tests for AudioExtractor."""

    def test_init_default_params(self) -> None:
        """Test initialization with default parameters."""
        extractor = AudioExtractor()

        assert extractor.sample_rate == 16000
        assert extractor.channels == 1

    def test_init_custom_params(self) -> None:
        """Test initialization with custom parameters."""
        extractor = AudioExtractor(sample_rate=44100, channels=2)

        assert extractor.sample_rate == 44100
        assert extractor.channels == 2

    def test_is_audio_file(self) -> None:
        """Test audio file detection."""
        extractor = AudioExtractor()

        assert extractor.is_audio_file(Path("test.wav"))
        assert extractor.is_audio_file(Path("test.mp3"))
        assert extractor.is_audio_file(Path("test.m4a"))
        assert not extractor.is_audio_file(Path("test.mp4"))
        assert not extractor.is_audio_file(Path("test.avi"))

    @patch("subprocess.run")
    def test_check_ffmpeg_available_success(self, mock_run: Mock) -> None:
        """Test FFmpeg availability check when available."""
        mock_run.return_value = Mock(returncode=0)
        extractor = AudioExtractor()

        assert extractor.check_ffmpeg_available() is True

    @patch("subprocess.run")
    def test_check_ffmpeg_available_not_found(self, mock_run: Mock) -> None:
        """Test FFmpeg availability check when not available."""
        mock_run.side_effect = FileNotFoundError()
        extractor = AudioExtractor()

        assert extractor.check_ffmpeg_available() is False

    @patch("subprocess.run")
    def test_extract_audio_file_not_found(self, mock_run: Mock) -> None:
        """Test extraction with non-existent file."""
        extractor = AudioExtractor()

        with pytest.raises(AudioExtractionError, match="Input file not found"):
            extractor.extract_audio(Path("/nonexistent/file.mp4"))

    @patch("subprocess.run")
    @patch.object(AudioExtractor, "check_ffmpeg_available", return_value=False)
    def test_extract_audio_ffmpeg_not_available(
        self, mock_check: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test extraction when FFmpeg is not available."""
        # Create a temporary video file
        video_file = tmp_path / "test.mp4"
        video_file.write_text("fake video")

        extractor = AudioExtractor()

        with pytest.raises(AudioExtractionError, match="FFmpeg is not installed"):
            extractor.extract_audio(video_file)


class TestTranscriptMerger:
    """Tests for TranscriptMerger."""

    def test_calculate_overlap_full_overlap(self) -> None:
        """Test overlap calculation with full overlap."""
        merger = TranscriptMerger()
        overlap = merger._calculate_overlap(0.0, 5.0, 0.0, 5.0)

        assert overlap == 5.0

    def test_calculate_overlap_partial_overlap(self) -> None:
        """Test overlap calculation with partial overlap."""
        merger = TranscriptMerger()
        overlap = merger._calculate_overlap(0.0, 5.0, 3.0, 8.0)

        assert overlap == 2.0

    def test_calculate_overlap_no_overlap(self) -> None:
        """Test overlap calculation with no overlap."""
        merger = TranscriptMerger()
        overlap = merger._calculate_overlap(0.0, 5.0, 6.0, 10.0)

        assert overlap == 0.0

    def test_calculate_overlap_touching(self) -> None:
        """Test overlap calculation with touching intervals."""
        merger = TranscriptMerger()
        overlap = merger._calculate_overlap(0.0, 5.0, 5.0, 10.0)

        assert overlap == 0.0

    def test_merge_single_speaker(self) -> None:
        """Test merging with single speaker."""
        merger = TranscriptMerger()

        transcripts = [
            TranscriptSegment(start=0.0, end=3.0, text="Hello"),
            TranscriptSegment(start=3.5, end=6.0, text="World"),
        ]

        speakers = [
            SpeakerSegment(start=0.0, end=10.0, speaker_id="SPEAKER_00"),
        ]

        merged = merger.merge(transcripts, speakers)

        assert len(merged) == 2
        assert merged[0].text == "Hello"
        assert merged[0].speaker == "SPEAKER_00"
        assert merged[1].text == "World"
        assert merged[1].speaker == "SPEAKER_00"

    def test_merge_multiple_speakers(self) -> None:
        """Test merging with multiple speakers."""
        merger = TranscriptMerger()

        transcripts = [
            TranscriptSegment(start=0.0, end=3.0, text="First speaker"),
            TranscriptSegment(start=4.0, end=7.0, text="Second speaker"),
        ]

        speakers = [
            SpeakerSegment(start=0.0, end=3.5, speaker_id="SPEAKER_00"),
            SpeakerSegment(start=3.5, end=8.0, speaker_id="SPEAKER_01"),
        ]

        merged = merger.merge(transcripts, speakers)

        assert len(merged) == 2
        assert merged[0].speaker == "SPEAKER_00"
        assert merged[1].speaker == "SPEAKER_01"

    def test_merge_no_speaker_segments(self) -> None:
        """Test merging with no speaker segments."""
        merger = TranscriptMerger()

        transcripts = [
            TranscriptSegment(start=0.0, end=3.0, text="Hello"),
        ]

        speakers: list[SpeakerSegment] = []

        merged = merger.merge(transcripts, speakers)

        assert len(merged) == 1
        assert merged[0].speaker == "SPEAKER_UNKNOWN"
        assert merged[0].confidence == 0.0

    def test_merge_confidence_calculation(self) -> None:
        """Test confidence calculation in merging."""
        merger = TranscriptMerger()

        # Transcript from 0-4, Speaker from 0-2 (50% overlap)
        transcripts = [
            TranscriptSegment(start=0.0, end=4.0, text="Test"),
        ]

        speakers = [
            SpeakerSegment(start=0.0, end=2.0, speaker_id="SPEAKER_00"),
        ]

        merged = merger.merge(transcripts, speakers)

        assert len(merged) == 1
        assert merged[0].confidence == 0.5  # 2.0 / 4.0


class TestSpeakerDiarizer:
    """Tests for SpeakerDiarizer."""

    @patch("debate_analyzer.transcriber.diarizer.Pipeline")
    def test_pipeline_moved_to_device_when_cpu_requested(
        self, mock_pipeline_class: Mock
    ) -> None:
        """SpeakerDiarizer moves the pipeline to the requested device (e.g. CPU)."""
        import torch

        from debate_analyzer.transcriber.diarizer import SpeakerDiarizer

        mock_pipeline = MagicMock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        SpeakerDiarizer(
            hf_token="test_token",
            pipeline_name="pyannote/speaker-diarization-3.1",
            device="cpu",
        )

        mock_pipeline.to.assert_called_once_with(torch.device("cpu"))


class TestTranscriptionConfig:
    """Tests for configuration loading."""

    def test_load_default_config(self, tmp_path: Path) -> None:
        """Test loading default configuration."""
        # Create a temporary config file
        config_path = tmp_path / "transcriber_conf.json"
        config_data = {
            "description": "Test config",
            "whisper": {
                "model_size": "medium",
                "device": "auto",
                "compute_type": "float16",
                "language": None,
            },
            "pyannote": {
                "pipeline": "pyannote/speaker-diarization-3.1",
                "min_speakers": None,
                "max_speakers": None,
            },
            "audio_extraction": {
                "sample_rate": 16000,
                "channels": 1,
                "format": "wav",
            },
        }

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # Import here to avoid issues
        from debate_analyzer.transcriber.transcriber import _load_config

        config = _load_config(config_path)

        assert "whisper" in config
        assert config["whisper"]["model_size"] == "medium"
        assert "pyannote" in config
        assert "audio_extraction" in config
        assert "description" not in config  # Should be removed


@pytest.mark.slow
@pytest.mark.integration
class TestTranscriptionIntegration:
    """Integration tests for full transcription pipeline.

    These tests require actual models and are marked as slow.
    Run with: pytest -m "not slow" to skip them.
    """

    @pytest.mark.skip(reason="Requires models and is time-consuming")
    def test_full_pipeline(self, tmp_path: Path) -> None:
        """Test full transcription pipeline with real models.

        This test is skipped by default as it requires:
        - Downloaded Whisper models (~5GB)
        - HuggingFace token
        - Significant processing time
        """
        from debate_analyzer.transcriber import transcribe_video

        # This would require a real video file and models
        video_path = tmp_path / "test_video.mp4"

        # Skip if video doesn't exist
        if not video_path.exists():
            pytest.skip("Test video not available")

        result = transcribe_video(
            video_path=video_path,
            output_dir=tmp_path / "output",
            model_size="tiny",  # Use smallest model for testing
        )

        assert "transcription" in result
        assert "speakers_count" in result
        assert "output_path" in result

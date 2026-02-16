"""Speech-to-text transcription using faster-whisper."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional, Union


def _format_duration(seconds: float) -> str:
    """Format seconds as M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _format_elapsed(seconds: float) -> str:
    """Format elapsed time for progress (e.g. 12.3s or 1m 23.4s)."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    m = int(seconds) // 60
    s = seconds - 60 * m
    return f"{m}m {s:.1f}s"

from faster_whisper import WhisperModel  # type: ignore[import-untyped]

from debate_analyzer.transcriber.audio_extractor import AudioExtractor
from debate_analyzer.transcriber.diarizer import SpeakerDiarizer
from debate_analyzer.transcriber.merger import TranscriptMerger
from debate_analyzer.transcriber.models import TranscriptSegment


class TranscriptionError(Exception):
    """Exception raised when transcription fails."""

    pass


class WhisperTranscriber:
    """Transcribes audio using faster-whisper."""

    def __init__(
        self,
        model_size: str = "medium",
        device: str = "auto",
        compute_type: str = "float16",
        language: Optional[str] = None,
        beam_size: int = 5,
        condition_on_previous_text: bool = True,
    ) -> None:
        """
        Initialize the Whisper transcriber.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large, etc.)
            device: Device to use ('auto', 'cpu', or 'cuda')
            compute_type: Computation type ('float16', 'int8', 'float32')
            language: Language code (e.g., 'en', 'es'). None for auto-detection.
            beam_size: Beam size for decoding (1 = greedy, faster; 5 = default quality).
            condition_on_previous_text: Use previous segment for context (false can speed long audio).
        """
        self.model_size = model_size
        self.language = language
        self.beam_size = beam_size
        self.condition_on_previous_text = condition_on_previous_text

        # Auto-detect device if requested
        if device == "auto":
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        self.device = device

        # Adjust compute type based on device
        if device == "cpu":
            compute_type = "int8"  # More efficient for CPU
        
        self.compute_type = compute_type

        try:
            # Load the model
            self.model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
            )
        except Exception as e:
            raise TranscriptionError(
                f"Failed to load Whisper model '{model_size}': {e}"
            ) from e

    def transcribe(
        self,
        audio_path: Union[str, Path],
        duration_sec: Optional[float] = None,
        step_start_time: Optional[float] = None,
    ) -> list[TranscriptSegment]:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            duration_sec: Total audio duration in seconds. If set, progress is
                printed during transcription (Step 2).
            step_start_time: Start time of the step (from time.time()). If set
                with duration_sec, elapsed time is shown with each progress update.

        Returns:
            List of transcript segments with timestamps

        Raises:
            TranscriptionError: If transcription fails
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        try:
            # Transcribe with word-level timestamps
            segments, info = self.model.transcribe(
                str(audio_path),
                language=self.language,
                word_timestamps=False,  # Segment-level is more reliable
                vad_filter=True,  # Voice activity detection
                beam_size=self.beam_size,
                condition_on_previous_text=self.condition_on_previous_text,
            )

            # Convert to our data model and optionally show progress
            transcript_segments = []
            last_reported_pct = -1
            show_progress = duration_sec is not None and duration_sec > 0

            for segment in segments:
                transcript_segments.append(
                    TranscriptSegment(
                        start=segment.start,
                        end=segment.end,
                        text=segment.text.strip(),
                    )
                )
                if show_progress:
                    pct = min(100, int(100 * segment.end / duration_sec))
                    if pct >= last_reported_pct + 5 or pct == 100:
                        elapsed_str = ""
                        if step_start_time is not None:
                            elapsed_str = (
                                f" — elapsed: {_format_elapsed(time.time() - step_start_time)}"
                            )
                        sys.stdout.write(
                            f"\r  Transcribing: {pct}% "
                            f"({_format_duration(segment.end)} / "
                            f"{_format_duration(duration_sec)}){elapsed_str}    "
                        )
                        sys.stdout.flush()
                        last_reported_pct = pct

            if show_progress:
                sys.stdout.write("\n")
                sys.stdout.flush()

            return transcript_segments

        except Exception as e:
            raise TranscriptionError(f"Failed to transcribe audio: {e}") from e


def transcribe_video(
    video_path: Union[str, Path],
    output_dir: Union[str, Path] = "data/transcripts",
    model_size: str = "medium",
    device: str = "auto",
    hf_token: Optional[str] = None,
    config_path: Union[str, Path, None] = None,
    language: Optional[str] = None,
) -> dict[str, Any]:
    """
    Transcribe video with speaker identification.

    This is the main API function that orchestrates the entire transcription
    pipeline: audio extraction, speech-to-text, speaker diarization, and merging.

    Args:
        video_path: Path to video file
        output_dir: Directory to save outputs (default: "data/transcripts")
        model_size: Whisper model size (default: "medium")
        device: Device to use ('auto', 'cpu', or 'cuda')
        hf_token: HuggingFace token for pyannote (or use HF_TOKEN env var)
        config_path: Path to custom configuration file (optional)
        language: Language code for transcription (e.g., 'en', 'es'). Auto-detected if None.

    Returns:
        Dictionary containing:
            - video_path: str - Path to input video
            - audio_path: str - Path to extracted audio
            - duration: float - Duration in seconds
            - processing_time: float - Total processing time
            - model: dict - Model information
            - speakers_count: int - Number of unique speakers
            - transcription: list - List of transcript segments with speakers
            - output_path: str - Path to output JSON file

    Raises:
        TranscriptionError: If transcription fails

    Example:
        >>> result = transcribe_video("debate.mp4")
        >>> print(f"Found {result['speakers_count']} speakers")
        >>> for seg in result['transcription']:
        ...     print(f"[{seg['speaker']}] {seg['text']}")
    """
    start_time = time.time()

    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        raise TranscriptionError(f"Video file not found: {video_path}")

    # Load configuration if provided
    config = _load_config(config_path)

    # Override config with provided parameters
    if model_size != "medium":
        config["whisper"]["model_size"] = model_size
    if language is not None:
        config["whisper"]["language"] = language

    # Step 1: Extract audio
    step_start = time.time()
    print("Step 1/4: Extracting audio from video...")
    extractor = AudioExtractor(
        sample_rate=config["audio_extraction"]["sample_rate"],
        channels=config["audio_extraction"]["channels"],
    )

    # Generate output audio path
    audio_filename = f"{video_path.stem}_audio.wav"
    audio_path = output_dir / audio_filename

    audio_path = extractor.extract_audio(video_path, audio_path)
    step_elapsed = time.time() - step_start
    total_elapsed = time.time() - start_time
    print(f"  Audio extracted to: {audio_path}")
    print(f"  Done in {_format_elapsed(step_elapsed)} (elapsed: {_format_elapsed(total_elapsed)})")

    # Get duration from audio file
    duration = _get_audio_duration(audio_path)

    # Step 2: Transcribe
    step_start = time.time()
    print("\nStep 2/4: Transcribing audio with Whisper...")
    transcriber = WhisperTranscriber(
        model_size=config["whisper"]["model_size"],
        device=device,
        compute_type=config["whisper"]["compute_type"],
        language=config["whisper"].get("language"),
        beam_size=config["whisper"].get("beam_size", 5),
        condition_on_previous_text=config["whisper"].get(
            "condition_on_previous_text", True
        ),
    )
    transcript_segments = transcriber.transcribe(
        audio_path,
        duration_sec=duration,
        step_start_time=step_start,
    )
    step_elapsed = time.time() - step_start
    total_elapsed = time.time() - start_time
    print(f"  Found {len(transcript_segments)} transcript segments")
    print(f"  Done in {_format_elapsed(step_elapsed)} (elapsed: {_format_elapsed(total_elapsed)})")

    # Step 3: Diarize
    step_start = time.time()
    print("\nStep 3/4: Identifying speakers with pyannote...")
    diarizer = SpeakerDiarizer(
        hf_token=hf_token,
        pipeline_name=config["pyannote"]["pipeline"],
        min_speakers=config["pyannote"]["min_speakers"],
        max_speakers=config["pyannote"]["max_speakers"],
    )
    speaker_segments = diarizer.diarize(audio_path)

    # Count unique speakers
    unique_speakers = len(set(seg.speaker_id for seg in speaker_segments))
    step_elapsed = time.time() - step_start
    total_elapsed = time.time() - start_time
    print(f"  Found {unique_speakers} unique speakers")
    print(f"  Done in {_format_elapsed(step_elapsed)} (elapsed: {_format_elapsed(total_elapsed)})")

    # Step 4: Merge
    step_start = time.time()
    print("\nStep 4/4: Merging transcription with speaker labels...")
    merger = TranscriptMerger()
    merged_segments = merger.merge(transcript_segments, speaker_segments)
    step_elapsed = time.time() - step_start
    total_elapsed = time.time() - start_time
    print(f"  Created {len(merged_segments)} final segments")
    print(f"  Done in {_format_elapsed(step_elapsed)} (elapsed: {_format_elapsed(total_elapsed)})")

    processing_time = time.time() - start_time
    print(f"\nTotal time: {_format_elapsed(processing_time)}")

    # Prepare output
    result = {
        "video_path": str(video_path),
        "audio_path": str(audio_path),
        "duration": duration,
        "processing_time": processing_time,
        "model": {
            "whisper": config["whisper"]["model_size"],
            "diarization": config["pyannote"]["pipeline"],
        },
        "speakers_count": unique_speakers,
        "transcription": [seg.to_dict() for seg in merged_segments],
    }

    # Save to JSON
    output_filename = f"{video_path.stem}_transcription.json"
    output_path = output_dir / output_filename
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    result["output_path"] = str(output_path)

    return result


def _load_config(config_path: Union[str, Path, None] = None) -> dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to configuration file. If None, uses default.

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        # Use default config
        config_path = (
            Path(__file__).parent.parent / "conf" / "transcriber_conf.json"
        )
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise TranscriptionError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config: dict[str, Any] = json.load(f)

    # Remove description field if present
    config.pop("description", None)

    return config


def _get_audio_duration(audio_path: Path) -> float:
    """
    Get duration of audio file using FFmpeg.

    Args:
        audio_path: Path to audio file

    Returns:
        Duration in seconds
    """
    try:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        # Fallback: estimate from file size (rough estimate)
        # For 16kHz mono PCM: ~32KB per second
        file_size = audio_path.stat().st_size
        return file_size / 32000.0

"""Transcriber module for video transcription with speaker identification."""

from debate_analyzer.transcriber.models import (
    TranscriptSegment,
    SpeakerSegment,
    TranscriptWithSpeaker,
)
from debate_analyzer.transcriber.audio_extractor import AudioExtractor
from debate_analyzer.transcriber.transcriber import WhisperTranscriber, transcribe_video
from debate_analyzer.transcriber.diarizer import SpeakerDiarizer
from debate_analyzer.transcriber.merger import TranscriptMerger

__all__ = [
    "transcribe_video",
    "TranscriptSegment",
    "SpeakerSegment",
    "TranscriptWithSpeaker",
    "AudioExtractor",
    "WhisperTranscriber",
    "SpeakerDiarizer",
    "TranscriptMerger",
]

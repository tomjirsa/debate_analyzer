"""Merge transcription segments with speaker labels."""

from typing import Optional

from debate_analyzer.transcriber.models import (
    SpeakerSegment,
    TranscriptSegment,
    TranscriptWithSpeaker,
)


class TranscriptMerger:
    """Merges transcription segments with speaker diarization."""

    def merge(
        self,
        transcript_segments: list[TranscriptSegment],
        speaker_segments: list[SpeakerSegment],
    ) -> list[TranscriptWithSpeaker]:
        """
        Merge transcription with speaker labels based on timestamp overlap.

        For each transcript segment, finds the speaker segment with maximum overlap.

        Args:
            transcript_segments: List of transcript segments from Whisper
            speaker_segments: List of speaker segments from pyannote

        Returns:
            List of merged segments with both text and speaker labels
        """
        merged: list[TranscriptWithSpeaker] = []

        for transcript in transcript_segments:
            # Find the speaker with maximum overlap
            speaker_id, confidence = self._find_speaker_for_segment(
                transcript, speaker_segments
            )

            merged.append(
                TranscriptWithSpeaker(
                    start=transcript.start,
                    end=transcript.end,
                    text=transcript.text,
                    speaker=speaker_id,
                    confidence=confidence,
                )
            )

        return merged

    def _find_speaker_for_segment(
        self,
        transcript: TranscriptSegment,
        speaker_segments: list[SpeakerSegment],
    ) -> tuple[str, float]:
        """
        Find the speaker for a transcript segment based on overlap.

        Args:
            transcript: A transcript segment
            speaker_segments: List of speaker segments

        Returns:
            Tuple of (speaker_id, confidence) where confidence is overlap ratio
        """
        max_overlap = 0.0
        best_speaker: Optional[str] = None

        for speaker_seg in speaker_segments:
            overlap = self._calculate_overlap(
                transcript.start,
                transcript.end,
                speaker_seg.start,
                speaker_seg.end,
            )

            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = speaker_seg.speaker_id

        # Calculate confidence as ratio of overlap to segment duration
        segment_duration = transcript.end - transcript.start
        if segment_duration > 0:
            confidence = max_overlap / segment_duration
        else:
            confidence = 0.0

        # If no speaker found, assign unknown
        if best_speaker is None:
            best_speaker = "SPEAKER_UNKNOWN"
            confidence = 0.0

        return best_speaker, confidence

    def _calculate_overlap(
        self,
        start1: float,
        end1: float,
        start2: float,
        end2: float,
    ) -> float:
        """
        Calculate overlap duration between two time intervals.

        Args:
            start1: Start time of first interval
            end1: End time of first interval
            start2: Start time of second interval
            end2: End time of second interval

        Returns:
            Overlap duration in seconds (0 if no overlap)
        """
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)

        if overlap_start < overlap_end:
            return overlap_end - overlap_start
        else:
            return 0.0

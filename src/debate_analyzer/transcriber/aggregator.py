"""Aggregate consecutive same-speaker segments with optional max duration cap."""

from __future__ import annotations

from debate_analyzer.transcriber.models import TranscriptWithSpeaker


def aggregate_segments(
    segments: list[TranscriptWithSpeaker],
    max_segment_duration_sec: float = 60.0,
) -> list[TranscriptWithSpeaker]:
    """
    Merge consecutive segments from the same speaker into one, with optional duration cap.

    When the same speaker has consecutive segments, they are merged (text concatenated
    with space, time range extended, confidence averaged). If adding the next segment
    would make the current run longer than max_segment_duration_sec, the current run
    is emitted and a new run starts. When max_segment_duration_sec is <= 0, no
    duration cap is applied (only same-speaker merging).

    Args:
        segments: Ordered list of segments (start, end, text, speaker, confidence).
        max_segment_duration_sec: Maximum duration in seconds for one output segment.
            If <= 0, no cap is applied.

    Returns:
        List of merged segments (same type and fields as input).
    """
    if not segments:
        return []

    result: list[TranscriptWithSpeaker] = []
    run_start = segments[0].start
    run_end = segments[0].end
    run_texts: list[str] = [segments[0].text]
    run_speaker = segments[0].speaker
    run_confidences: list[float] = [segments[0].confidence]

    for seg in segments[1:]:
        seg_dur = seg.end - seg.start
        run_dur = run_end - run_start
        same_speaker = seg.speaker == run_speaker
        no_cap = max_segment_duration_sec <= 0
        under_cap = no_cap or (run_dur + seg_dur <= max_segment_duration_sec)

        if same_speaker and under_cap:
            run_end = seg.end
            run_texts.append(seg.text)
            run_confidences.append(seg.confidence)
        else:
            # Emit current run
            text = " ".join(t.strip() for t in run_texts if t.strip())
            avg_conf = (
                sum(run_confidences) / len(run_confidences)
                if run_confidences
                else 1.0
            )
            result.append(
                TranscriptWithSpeaker(
                    start=run_start,
                    end=run_end,
                    text=text,
                    speaker=run_speaker,
                    confidence=avg_conf,
                )
            )
            run_start = seg.start
            run_end = seg.end
            run_texts = [seg.text]
            run_speaker = seg.speaker
            run_confidences = [seg.confidence]

    text = " ".join(t.strip() for t in run_texts if t.strip())
    avg_conf = (
        sum(run_confidences) / len(run_confidences) if run_confidences else 1.0
    )
    result.append(
        TranscriptWithSpeaker(
            start=run_start,
            end=run_end,
            text=text,
            speaker=run_speaker,
            confidence=avg_conf,
        )
    )
    return result

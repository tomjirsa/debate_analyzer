"""Repository layer: create/list transcripts, speaker profiles, and mappings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from debate_analyzer.db.models import (
    Segment,
    SpeakerMapping,
    SpeakerProfile,
    SpeakerStatGroup,
    Transcript,
    TranscriptSpeakerStats,
)


class TranscriptRepository:
    """Repository for transcripts, segments, speaker profiles, and mappings."""

    def __init__(self, session: Session) -> None:
        """Initialize with a SQLAlchemy session."""
        self.session = session

    def create_transcript_from_payload(
        self,
        source_uri: str,
        payload: dict[str, Any],
        source_type: str = "s3",
        title: str | None = None,
    ) -> Transcript:
        """
        Create a Transcript and Segment rows from transcript JSON payload.
        Creates empty SpeakerMapping rows for each distinct speaker_id_in_transcript.
        Idempotent by source_uri: if transcript exists, returns it without duplicating.
        """
        existing = (
            self.session.query(Transcript)
            .filter(Transcript.source_uri == source_uri)
            .first()
        )
        if existing:
            return existing

        transcription = payload.get("transcription") or []
        duration = payload.get("duration")
        video_path = payload.get("video_path")
        speakers_count = payload.get("speakers_count")
        model_info = payload.get("model")
        processing_time = payload.get("processing_time")

        meta: dict[str, Any] = {}
        if model_info is not None:
            meta["model"] = model_info
        if processing_time is not None:
            meta["processing_time"] = processing_time

        transcript = Transcript(
            source_type=source_type,
            source_uri=source_uri,
            title=title or source_uri.split("/")[-1].replace("_transcription.json", ""),
            duration=duration,
            video_path=str(video_path) if video_path else None,
            speakers_count=speakers_count,
            metadata_=meta if meta else None,
        )
        self.session.add(transcript)
        self.session.flush()

        seen_speakers: set[str] = set()
        for seg in transcription:
            start = seg.get("start")
            end = seg.get("end")
            text = seg.get("text") or ""
            speaker = seg.get("speaker") or "SPEAKER_UNKNOWN"
            confidence = seg.get("confidence")

            self.session.add(
                Segment(
                    transcript_id=transcript.id,
                    start=float(start) if start is not None else 0.0,
                    end=float(end) if end is not None else 0.0,
                    text=text,
                    speaker_id_in_transcript=speaker,
                    confidence=float(confidence) if confidence is not None else None,
                )
            )
            seen_speakers.add(speaker)

        for speaker_id in seen_speakers:
            self.session.add(
                SpeakerMapping(
                    transcript_id=transcript.id,
                    speaker_id_in_transcript=speaker_id,
                    speaker_profile_id=None,
                )
            )

        self.session.commit()
        self.session.refresh(transcript)
        return transcript

    def get_transcript_by_id(self, transcript_id: str) -> Transcript | None:
        """Return transcript by id or None."""
        return (
            self.session.query(Transcript)
            .filter(Transcript.id == transcript_id)
            .first()
        )

    def get_transcript_by_source_uri(self, source_uri: str) -> Transcript | None:
        """Return transcript by source_uri or None."""
        return (
            self.session.query(Transcript)
            .filter(Transcript.source_uri == source_uri)
            .first()
        )

    def list_transcripts(self, limit: int = 100, offset: int = 0) -> list[Transcript]:
        """List transcripts ordered by created_at desc."""
        return (
            self.session.query(Transcript)
            .order_by(Transcript.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def update_transcript(
        self,
        transcript_id: str,
        title: str | None = None,
        video_path: str | None = None,
    ) -> Transcript | None:
        """Update transcript title and/or video_path.
        Returns updated transcript or None if not found.
        """
        transcript = self.get_transcript_by_id(transcript_id)
        if not transcript:
            return None
        if title is not None:
            transcript.title = title
        if video_path is not None:
            transcript.video_path = video_path
        self.session.commit()
        self.session.refresh(transcript)
        return transcript

    def delete_transcript(self, transcript_id: str) -> bool:
        """Delete transcript (cascades to segments and mappings).
        Returns True if deleted, False if not found.
        """
        transcript = self.get_transcript_by_id(transcript_id)
        if not transcript:
            return False
        self.session.delete(transcript)
        self.session.commit()
        return True

    def get_speaker_profile_by_id(self, profile_id: str) -> SpeakerProfile | None:
        """Return speaker profile by id or None."""
        return (
            self.session.query(SpeakerProfile)
            .filter(SpeakerProfile.id == profile_id)
            .first()
        )

    def get_speaker_profile_by_slug(self, slug: str) -> SpeakerProfile | None:
        """Return speaker profile by slug or None."""
        return (
            self.session.query(SpeakerProfile)
            .filter(SpeakerProfile.slug == slug)
            .first()
        )

    def create_speaker_profile(
        self,
        first_name: str,
        surname: str,
        slug: str | None = None,
        bio: str | None = None,
        short_description: str | None = None,
    ) -> SpeakerProfile:
        """Create a new speaker profile."""
        profile = SpeakerProfile(
            first_name=first_name,
            surname=surname,
            slug=slug,
            bio=bio,
            short_description=short_description,
        )
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def update_speaker_profile(
        self,
        profile_id: str,
        first_name: str | None = None,
        surname: str | None = None,
        slug: str | None = None,
        bio: str | None = None,
        short_description: str | None = None,
    ) -> SpeakerProfile | None:
        """Update a speaker profile by id. Returns the profile or None if not found."""
        profile = self.get_speaker_profile_by_id(profile_id)
        if not profile:
            return None
        if first_name is not None:
            profile.first_name = first_name
        if surname is not None:
            profile.surname = surname
        if slug is not None:
            profile.slug = slug
        if bio is not None:
            profile.bio = bio
        if short_description is not None:
            profile.short_description = short_description
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def delete_speaker_profile(self, profile_id: str) -> bool:
        """Delete speaker profile by id (mappings CASCADE). Returns True if deleted."""
        profile = self.get_speaker_profile_by_id(profile_id)
        if not profile:
            return False
        self.session.delete(profile)
        self.session.commit()
        return True

    def list_speaker_profiles(self, limit: int = 200) -> list[SpeakerProfile]:
        """List all speaker profiles ordered by surname, then first_name."""
        return (
            self.session.query(SpeakerProfile)
            .order_by(SpeakerProfile.surname, SpeakerProfile.first_name)
            .limit(limit)
            .all()
        )

    def get_mappings_for_transcript(self, transcript_id: str) -> list[SpeakerMapping]:
        """Return all speaker mappings for a transcript."""
        return (
            self.session.query(SpeakerMapping)
            .filter(SpeakerMapping.transcript_id == transcript_id)
            .all()
        )

    def save_mapping(
        self,
        transcript_id: str,
        speaker_id_in_transcript: str,
        speaker_profile_id: str | None,
    ) -> SpeakerMapping | None:
        """Set or clear speaker_profile_id for this transcript/speaker_id pair."""
        col = SpeakerMapping.speaker_id_in_transcript
        mapping = (
            self.session.query(SpeakerMapping)
            .filter(
                SpeakerMapping.transcript_id == transcript_id,
                col == speaker_id_in_transcript,
            )
            .first()
        )
        if not mapping:
            return None
        mapping.speaker_profile_id = speaker_profile_id
        self.session.commit()
        self.session.refresh(mapping)
        return mapping

    def save_mappings_bulk(
        self,
        transcript_id: str,
        mapping: dict[str, str | None],
    ) -> None:
        """
        mapping: speaker_id_in_transcript -> speaker_profile_id (or None to unset).
        """
        for speaker_id_in_transcript, speaker_profile_id in mapping.items():
            self.save_mapping(
                transcript_id, speaker_id_in_transcript, speaker_profile_id
            )

    def get_speaker_stats(self, speaker_profile_id: str) -> dict[str, Any]:
        """
        Aggregate stats for a speaker from segments and from transcript_speaker_stats.

        Core stats (total_seconds, segment_count, word_count) come from Segment.
        Extended stats (turn_count, shortest/longest talk, shares, etc.) are
        aggregated from TranscriptSpeakerStats so the speaker profile UI can show
        all stat groups.
        """
        q = (
            self.session.query(Segment)
            .join(
                SpeakerMapping,
                (Segment.transcript_id == SpeakerMapping.transcript_id)
                & (
                    Segment.speaker_id_in_transcript
                    == SpeakerMapping.speaker_id_in_transcript
                ),
            )
            .filter(SpeakerMapping.speaker_profile_id == speaker_profile_id)
        )
        segments = q.all()
        total_seconds = sum(s.end - s.start for s in segments)
        segment_count = len(segments)
        transcript_count = (
            self.session.query(func.count(func.distinct(SpeakerMapping.transcript_id)))
            .filter(SpeakerMapping.speaker_profile_id == speaker_profile_id)
            .scalar()
        )
        word_count = sum(len((s.text or "").split()) for s in segments)
        wpm = (
            (word_count / (total_seconds / 60.0))
            if total_seconds and total_seconds > 0
            else None
        )
        avg_segment_duration_sec = (
            (total_seconds / segment_count) if segment_count else None
        )
        result: dict[str, Any] = {
            "total_seconds": total_seconds,
            "segment_count": segment_count,
            "transcript_count": int(transcript_count or 0),
            "word_count": word_count,
            "wpm": wpm,
            "avg_segment_duration_sec": avg_segment_duration_sec,
        }
        # Aggregate extended stats from transcript_speaker_stats for this speaker
        tss_rows = (
            self.session.query(TranscriptSpeakerStats)
            .join(
                SpeakerMapping,
                (TranscriptSpeakerStats.transcript_id == SpeakerMapping.transcript_id)
                & (
                    TranscriptSpeakerStats.speaker_id_in_transcript
                    == SpeakerMapping.speaker_id_in_transcript
                ),
            )
            .filter(SpeakerMapping.speaker_profile_id == speaker_profile_id)
            .all()
        )
        if not tss_rows:
            return result
        shorts = [r.shortest_talk_sec for r in tss_rows if r.shortest_talk_sec is not None]
        longs = [r.longest_talk_sec for r in tss_rows if r.longest_talk_sec is not None]
        medians = [
            r.median_segment_duration_sec
            for r in tss_rows
            if r.median_segment_duration_sec is not None
        ]
        turn_counts = [r.turn_count for r in tss_rows if r.turn_count is not None]
        share_time = [
            r.share_speaking_time
            for r in tss_rows
            if r.share_speaking_time is not None
        ]
        share_w = [r.share_words for r in tss_rows if r.share_words is not None]
        total_turns = sum(turn_counts) if turn_counts else 0
        result["shortest_talk_sec"] = min(shorts) if shorts else None
        result["longest_talk_sec"] = max(longs) if longs else None
        result["median_segment_duration_sec"] = (
            sum(medians) / len(medians) if medians else None
        )
        result["turn_count"] = total_turns if total_turns else None
        result["avg_turn_length_sec"] = (
            (total_seconds / total_turns) if total_turns else None
        )
        result["avg_turn_length_segments"] = (
            (segment_count / total_turns) if total_turns else None
        )
        result["is_first_speaker"] = any(r.is_first_speaker for r in tss_rows)
        result["is_last_speaker"] = any(r.is_last_speaker for r in tss_rows)
        result["share_speaking_time"] = (
            sum(share_time) / len(share_time) if share_time else None
        )
        result["share_words"] = (
            sum(share_w) / len(share_w) if share_w else None
        )
        return result

    def save_transcript_speaker_stats(
        self,
        transcript_id: str,
        rows: list[dict[str, Any]],
    ) -> None:
        """
        Replace all speaker stats for a transcript with the given rows.
        Idempotent: deletes existing rows for this transcript then inserts.
        """
        self.session.query(TranscriptSpeakerStats).filter(
            TranscriptSpeakerStats.transcript_id == transcript_id
        ).delete()
        for row in rows:
            self.session.add(
                TranscriptSpeakerStats(
                    transcript_id=transcript_id,
                    speaker_id_in_transcript=row["speaker_id_in_transcript"],
                    total_seconds=float(row["total_seconds"]),
                    segment_count=int(row["segment_count"]),
                    word_count=int(row["word_count"]),
                    wpm=float(row["wpm"]) if row.get("wpm") is not None else None,
                    avg_segment_duration_sec=(
                        float(row["avg_segment_duration_sec"])
                        if row.get("avg_segment_duration_sec") is not None
                        else None
                    ),
                    shortest_talk_sec=(
                        float(row["shortest_talk_sec"])
                        if row.get("shortest_talk_sec") is not None
                        else None
                    ),
                    longest_talk_sec=(
                        float(row["longest_talk_sec"])
                        if row.get("longest_talk_sec") is not None
                        else None
                    ),
                    median_segment_duration_sec=(
                        float(row["median_segment_duration_sec"])
                        if row.get("median_segment_duration_sec") is not None
                        else None
                    ),
                    turn_count=(
                        int(row["turn_count"])
                        if row.get("turn_count") is not None
                        else None
                    ),
                    avg_turn_length_sec=(
                        float(row["avg_turn_length_sec"])
                        if row.get("avg_turn_length_sec") is not None
                        else None
                    ),
                    avg_turn_length_segments=(
                        float(row["avg_turn_length_segments"])
                        if row.get("avg_turn_length_segments") is not None
                        else None
                    ),
                    is_first_speaker=bool(row.get("is_first_speaker", False)),
                    is_last_speaker=bool(row.get("is_last_speaker", False)),
                    share_speaking_time=(
                        float(row["share_speaking_time"])
                        if row.get("share_speaking_time") is not None
                        else None
                    ),
                    share_words=(
                        float(row["share_words"])
                        if row.get("share_words") is not None
                        else None
                    ),
                )
            )
        self.session.commit()

    def get_speaker_stats_for_transcript(
        self, transcript_id: str
    ) -> list[dict[str, Any]]:
        """Return per-speaker stats for a transcript (for admin transcript view)."""
        rows = (
            self.session.query(TranscriptSpeakerStats)
            .filter(TranscriptSpeakerStats.transcript_id == transcript_id)
            .all()
        )
        return [
            {
                "speaker_id_in_transcript": r.speaker_id_in_transcript,
                "total_seconds": r.total_seconds,
                "segment_count": r.segment_count,
                "word_count": r.word_count,
                "wpm": r.wpm,
                "avg_segment_duration_sec": r.avg_segment_duration_sec,
                "shortest_talk_sec": r.shortest_talk_sec,
                "longest_talk_sec": r.longest_talk_sec,
                "median_segment_duration_sec": r.median_segment_duration_sec,
                "turn_count": r.turn_count,
                "avg_turn_length_sec": r.avg_turn_length_sec,
                "avg_turn_length_segments": r.avg_turn_length_segments,
                "is_first_speaker": r.is_first_speaker,
                "is_last_speaker": r.is_last_speaker,
                "share_speaking_time": r.share_speaking_time,
                "share_words": r.share_words,
            }
            for r in rows
        ]

    def get_stat_definitions(self) -> list[dict[str, Any]]:
        """
        Return stat groups with their stat definitions for UI (grouped display).

        Returns:
            List of dicts: { key, label, sort_order, stats: [ { stat_key, label,
            sort_order } ] }.
        """
        groups = (
            self.session.query(SpeakerStatGroup)
            .options(joinedload(SpeakerStatGroup.stat_definitions))
            .order_by(SpeakerStatGroup.sort_order)
            .all()
        )
        return [
            {
                "key": g.key,
                "label": g.label,
                "sort_order": g.sort_order,
                "stats": [
                    {
                        "stat_key": d.stat_key,
                        "label": d.label,
                        "sort_order": d.sort_order,
                    }
                    for d in g.stat_definitions
                ],
            }
            for g in groups
        ]

    def get_speaker_stats_by_transcript(
        self, speaker_profile_id: str
    ) -> list[dict[str, Any]]:
        """
        Return per-transcript stats for a speaker (for public speaker page breakdown).
        Joins transcript_speaker_stats with speaker_mapping and transcript.
        """
        q = (
            self.session.query(
                TranscriptSpeakerStats.transcript_id,
                Transcript.title.label("transcript_title"),
                TranscriptSpeakerStats.total_seconds,
                TranscriptSpeakerStats.segment_count,
                TranscriptSpeakerStats.word_count,
                TranscriptSpeakerStats.wpm,
                TranscriptSpeakerStats.avg_segment_duration_sec,
                TranscriptSpeakerStats.shortest_talk_sec,
                TranscriptSpeakerStats.longest_talk_sec,
                TranscriptSpeakerStats.median_segment_duration_sec,
                TranscriptSpeakerStats.turn_count,
                TranscriptSpeakerStats.avg_turn_length_sec,
                TranscriptSpeakerStats.avg_turn_length_segments,
                TranscriptSpeakerStats.is_first_speaker,
                TranscriptSpeakerStats.is_last_speaker,
                TranscriptSpeakerStats.share_speaking_time,
                TranscriptSpeakerStats.share_words,
            )
            .join(
                SpeakerMapping,
                (TranscriptSpeakerStats.transcript_id == SpeakerMapping.transcript_id)
                & (
                    TranscriptSpeakerStats.speaker_id_in_transcript
                    == SpeakerMapping.speaker_id_in_transcript
                ),
            )
            .join(Transcript, TranscriptSpeakerStats.transcript_id == Transcript.id)
            .filter(SpeakerMapping.speaker_profile_id == speaker_profile_id)
            .order_by(Transcript.created_at.desc())
        )
        rows = q.all()
        return [
            {
                "transcript_id": r.transcript_id,
                "transcript_title": r.transcript_title,
                "total_seconds": r.total_seconds,
                "segment_count": r.segment_count,
                "word_count": r.word_count,
                "wpm": r.wpm,
                "avg_segment_duration_sec": r.avg_segment_duration_sec,
                "shortest_talk_sec": r.shortest_talk_sec,
                "longest_talk_sec": r.longest_talk_sec,
                "median_segment_duration_sec": r.median_segment_duration_sec,
                "turn_count": r.turn_count,
                "avg_turn_length_sec": r.avg_turn_length_sec,
                "avg_turn_length_segments": r.avg_turn_length_segments,
                "is_first_speaker": r.is_first_speaker,
                "is_last_speaker": r.is_last_speaker,
                "share_speaking_time": r.share_speaking_time,
                "share_words": r.share_words,
            }
            for r in rows
        ]

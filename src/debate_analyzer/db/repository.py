"""Repository layer: create/list transcripts, speaker profiles, and mappings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from debate_analyzer.db.models import (
    Segment,
    SpeakerMapping,
    SpeakerProfile,
    Transcript,
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
        Aggregate stats for a speaker: total_seconds, segment_count, transcript_count,
        word_count. Uses Segment joined with SpeakerMapping for this profile.
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
        return {
            "total_seconds": total_seconds,
            "segment_count": segment_count,
            "transcript_count": int(transcript_count or 0),
            "word_count": word_count,
        }

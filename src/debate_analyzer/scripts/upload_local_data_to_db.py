#!/usr/bin/env python3
"""
Local data uploader.

Scans `./data/*/transcripts/*_transcription.json` and imports transcript
segments, speaker mappings, and companion stats artifacts into the SQLite DB
used by local development.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from debate_analyzer.api.loader import (
    load_speaker_stats_parquet,
    load_transcript_payload,
    load_transcript_stats_json,
)
from debate_analyzer.db import TranscriptRepository, init_db
from debate_analyzer.db.base import get_session_factory
from debate_analyzer.db.models import (
    Group,
    SpeakerStatDefinition,
    SpeakerStatGroup,
)


@dataclass(frozen=True)
class UploadResult:
    """Summary of an upload run."""

    transcripts_seen: int
    transcripts_imported: int
    speaker_profiles_created: int
    mappings_set: int
    speaker_stats_imported: int
    transcript_stats_imported: int
    llm_analysis_imported: int
    stat_definitions_seeded: bool


def _slugify(text: str) -> str:
    """Convert input to a stable slug-like string."""

    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _speaker_profile_slug(speaker_id_in_transcript: str) -> str:
    """Return stable slug for a diarization speaker label."""

    # SPEAKER_00 -> speaker-00
    return _slugify(speaker_id_in_transcript)


def _dummy_speaker_names(speaker_id_in_transcript: str) -> tuple[str, str]:
    """Return dummy (first_name, surname) for the given speaker id."""

    # speaker-00 -> ("Speaker", "00")
    slug = _speaker_profile_slug(speaker_id_in_transcript)
    if slug.startswith("speaker-"):
        suffix = slug[len("speaker-") :]
        return "Speaker", suffix or "Unknown"
    return "Speaker", _speaker_profile_slug(speaker_id_in_transcript) or "Unknown"


def _get_or_create_group(
    repo: TranscriptRepository,
    *,
    group_slug: str,
    group_name: str,
    description: str | None,
) -> Group:
    """Get group by slug or create it if missing."""

    group = repo.get_group_by_slug(group_slug)
    if group:
        return group
    return repo.create_group(name=group_name, slug=group_slug, description=description)


def _seed_stat_definitions_if_empty(session: Session) -> bool:
    """Seed SpeakerStatGroup/SpeakerStatDefinition if there are none.

    Returns:
        True if we seeded, otherwise False.
    """

    existing = session.query(SpeakerStatGroup).first()
    if existing is not None:
        return False

    core = SpeakerStatGroup(key="core", label="Core statistics", sort_order=0)
    extended = SpeakerStatGroup(
        key="extended",
        label="Turn-taking & shares",
        sort_order=1,
    )
    session.add(core)
    session.add(extended)
    session.flush()  # populate group ids for FK relationship

    core_defs: list[SpeakerStatDefinition] = [
        SpeakerStatDefinition(
            stat_key="total_seconds",
            group_id=core.id,
            label="Speaking time (sec)",
            sort_order=0,
        ),
        SpeakerStatDefinition(
            stat_key="segment_count",
            group_id=core.id,
            label="Segments",
            sort_order=1,
        ),
        SpeakerStatDefinition(
            stat_key="word_count",
            group_id=core.id,
            label="Words",
            sort_order=2,
        ),
    ]

    extended_defs: list[SpeakerStatDefinition] = [
        SpeakerStatDefinition(
            stat_key="wpm",
            group_id=extended.id,
            label="Words per minute",
            sort_order=0,
        ),
        SpeakerStatDefinition(
            stat_key="avg_segment_duration_sec",
            group_id=extended.id,
            label="Avg segment duration (sec)",
            sort_order=1,
        ),
        SpeakerStatDefinition(
            stat_key="shortest_talk_sec",
            group_id=extended.id,
            label="Shortest talk (sec)",
            sort_order=2,
        ),
        SpeakerStatDefinition(
            stat_key="longest_talk_sec",
            group_id=extended.id,
            label="Longest talk (sec)",
            sort_order=3,
        ),
        SpeakerStatDefinition(
            stat_key="median_segment_duration_sec",
            group_id=extended.id,
            label="Median segment duration (sec)",
            sort_order=4,
        ),
        SpeakerStatDefinition(
            stat_key="turn_count",
            group_id=extended.id,
            label="Turn count",
            sort_order=5,
        ),
        SpeakerStatDefinition(
            stat_key="avg_turn_length_sec",
            group_id=extended.id,
            label="Avg turn length (sec)",
            sort_order=6,
        ),
        SpeakerStatDefinition(
            stat_key="avg_turn_length_segments",
            group_id=extended.id,
            label="Avg turn length (segments)",
            sort_order=7,
        ),
        SpeakerStatDefinition(
            stat_key="is_first_speaker",
            group_id=extended.id,
            label="First speaker",
            sort_order=8,
        ),
        SpeakerStatDefinition(
            stat_key="is_last_speaker",
            group_id=extended.id,
            label="Last speaker",
            sort_order=9,
        ),
        SpeakerStatDefinition(
            stat_key="share_speaking_time",
            group_id=extended.id,
            label="Share of speaking time",
            sort_order=10,
        ),
        SpeakerStatDefinition(
            stat_key="share_words",
            group_id=extended.id,
            label="Share of words",
            sort_order=11,
        ),
    ]

    session.add_all(core_defs)
    session.add_all(extended_defs)
    session.commit()
    return True


def upload_local_data_to_db(
    *,
    data_root: Path,
    session: Session,
    group_slug: str = "default",
    group_name: str = "Default",
    description: str | None = None,
    seed_stat_definitions: bool = True,
    import_llm_analysis: bool = False,
) -> UploadResult:
    """Upload local transcript artifacts into the database.

    The scan is performed relative to `data_root`:
    `data_root/*/transcripts/*_transcription.json`.

    Args:
        data_root: Root directory that contains job folders.
        session: SQLAlchemy session connected to the target DB.
        group_slug: Content group slug to import transcripts/speakers into.
        group_name: Group display name when creating the group.
        description: Optional group description.
        seed_stat_definitions: Seed default stat groups if none exist.
        import_llm_analysis: Import `_llm_analysis.json` if present.

    Returns:
        UploadResult summary.
    """

    if not data_root.exists():
        raise FileNotFoundError(f"data_root does not exist: {data_root}")

    repo = TranscriptRepository(session)
    group = _get_or_create_group(
        repo,
        group_slug=group_slug,
        group_name=group_name,
        description=description,
    )

    stat_definitions_seeded = False
    if seed_stat_definitions:
        stat_definitions_seeded = _seed_stat_definitions_if_empty(session)

    transcription_files = sorted(data_root.glob("*/*/transcripts/*_transcription.json"))
    if not transcription_files:
        # Allow `data_root` to be already `./data/<job-id>/transcripts`
        transcription_files = sorted(
            data_root.glob("*/transcripts/*_transcription.json")
        )

    transcripts_seen = len(transcription_files)
    transcripts_imported = 0
    speaker_profiles_created = 0
    mappings_set = 0
    speaker_stats_imported = 0
    transcript_stats_imported = 0
    llm_analysis_imported = 0

    for path in transcription_files:
        source_uri = f"file://{path.resolve()}"
        # Skip if transcript already exists.
        existing = repo.get_transcript_by_source_uri(source_uri)
        if existing is None:
            payload = load_transcript_payload(source_uri)
            transcript = repo.create_transcript_from_payload(
                source_uri=source_uri,
                payload=payload,
                source_type="file",
                group_id=group.id,
            )
            transcripts_imported += 1
        else:
            transcript = existing
            payload = load_transcript_payload(source_uri)

        transcription = payload.get("transcription") or []
        speaker_ids: set[str] = set()
        for seg in transcription:
            speaker_ids.add(seg.get("speaker") or "SPEAKER_UNKNOWN")

        # Create dummy speaker profiles + mapping assignment.
        mapping: dict[str, str | None] = {}
        for speaker_id_in_transcript in speaker_ids:
            slug = _speaker_profile_slug(speaker_id_in_transcript)
            profile = repo.get_speaker_profile_by_slug(
                slug,
                group_id=group.id,
            )
            if profile is None:
                first_name, surname = _dummy_speaker_names(speaker_id_in_transcript)
                profile = repo.create_speaker_profile(
                    first_name=first_name,
                    surname=surname,
                    group_id=group.id,
                    slug=slug,
                    bio=f"Imported dummy profile for {speaker_id_in_transcript}.",
                    short_description="Auto-created by local data uploader.",
                )
                speaker_profiles_created += 1
            mapping[speaker_id_in_transcript] = profile.id

        if mapping:
            repo.save_mappings_bulk(transcript.id, mapping)
            mappings_set += len(mapping)

        # Import speaker stats parquet if present.
        parquet_uri = source_uri.replace(
            "_transcription.json", "_speaker_stats.parquet"
        )
        parquet_rows = load_speaker_stats_parquet(parquet_uri)
        if parquet_rows:
            repo.save_transcript_speaker_stats(transcript.id, parquet_rows)
            speaker_stats_imported += 1

        # Import transcript-level stats JSON if present.
        stats = load_transcript_stats_json(source_uri)
        if stats:
            updated = repo.update_transcript_stats(transcript.id, **stats)
            if updated:
                transcript_stats_imported += 1

        # Optional LLM analysis import if present.
        if import_llm_analysis:
            existing_analysis = repo.get_latest_llm_analysis(transcript.id)
            if existing_analysis is None:
                analysis_uri = source_uri.replace(
                    "_transcription.json", "_llm_analysis.json"
                )
                try:
                    analysis_payload = load_transcript_payload(analysis_uri)
                except FileNotFoundError:
                    analysis_payload = None
                except ValueError:
                    analysis_payload = None

                if analysis_payload is not None:
                    result = analysis_payload.get("result", analysis_payload)
                    has_contributions = isinstance(result, dict) and isinstance(
                        result.get("speaker_contributions"), list
                    )
                    has_segment_summaries = isinstance(result, dict) and isinstance(
                        result.get("segment_summaries"), list
                    )
                    if has_contributions or has_segment_summaries:
                        repo.create_llm_analysis(
                            transcript_id=transcript.id,
                            model_name="batch",
                            result=result,
                            source="batch",
                        )
                        llm_analysis_imported += 1

    return UploadResult(
        transcripts_seen=transcripts_seen,
        transcripts_imported=transcripts_imported,
        speaker_profiles_created=speaker_profiles_created,
        mappings_set=mappings_set,
        speaker_stats_imported=speaker_stats_imported,
        transcript_stats_imported=transcript_stats_imported,
        llm_analysis_imported=llm_analysis_imported,
        stat_definitions_seeded=stat_definitions_seeded,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""

    parser = argparse.ArgumentParser(description="Upload local data into the DB.")
    parser.add_argument(
        "--data-root",
        type=str,
        default=str(Path("./data").resolve()),
        help="Root directory containing job folders and transcripts.",
    )
    parser.add_argument(
        "--group-slug",
        type=str,
        default="default",
        help="Content group slug to import into.",
    )
    parser.add_argument(
        "--group-name",
        type=str,
        default="Default",
        help="Group display name (used if group does not exist).",
    )
    parser.add_argument(
        "--no-seed-stat-definitions",
        action="store_true",
        help="Do not insert default stat groups/definitions.",
    )
    parser.add_argument(
        "--import-llm-analysis",
        action="store_true",
        help="Import *_llm_analysis.json when present (idempotent by transcript).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Ensure schema exists.
    init_db()
    session_factory = get_session_factory()
    session = session_factory()
    try:
        result = upload_local_data_to_db(
            data_root=Path(args.data_root),
            session=session,
            group_slug=args.group_slug,
            group_name=args.group_name,
            seed_stat_definitions=not args.no_seed_stat_definitions,
            import_llm_analysis=args.import_llm_analysis,
        )
    finally:
        session.close()

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

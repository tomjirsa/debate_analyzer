from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from debate_analyzer.db import Base
from debate_analyzer.db.models import (
    Group,
    SpeakerMapping,
    SpeakerProfile,
    SpeakerStatGroup,
    Transcript,
    TranscriptSpeakerStats,
)
from debate_analyzer.scripts.upload_local_data_to_db import upload_local_data_to_db
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def session() -> Session:
    """In-memory SQLite session with all tables created."""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()


def _write_parquet_speaker_stats(path: Path) -> None:
    """Write minimal speaker stats parquet with required columns."""

    table = pa.table(
        {
            "speaker_id_in_transcript": ["SPEAKER_00", "SPEAKER_01"],
            "total_seconds": [10.0, 20.0],
            "segment_count": [1, 2],
            "word_count": [3, 4],
        }
    )
    pq.write_table(table, str(path))


def test_upload_local_data_to_db_creates_profiles_mappings_and_stats(
    session: Session, tmp_path: Path
) -> None:
    """Populates transcripts, dummy speakers, mappings, and stats."""

    data_root = tmp_path / "data"
    job_dir = data_root / "job-1" / "transcripts"
    job_dir.mkdir(parents=True)

    transcription_path = job_dir / "sample_transcription.json"
    transcription_path.write_text(
        json.dumps(
            {
                "duration": 30.0,
                "video_path": "/tmp/v.mp4",
                "speakers_count": 2,
                "transcription": [
                    {
                        "start": 0.0,
                        "end": 10.0,
                        "text": "hello",
                        "speaker": "SPEAKER_00",
                    },
                    {
                        "start": 10.0,
                        "end": 20.0,
                        "text": "world",
                        "speaker": "SPEAKER_01",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _write_parquet_speaker_stats(job_dir / "sample_speaker_stats.parquet")
    (job_dir / "sample_transcript_stats.json").write_text(
        json.dumps(
            {
                "total_seconds": 30.0,
                "total_words": 7,
                "segment_count": 3,
                "speaker_count": 2,
            }
        ),
        encoding="utf-8",
    )

    result1 = upload_local_data_to_db(
        data_root=data_root,
        session=session,
        seed_stat_definitions=True,
        import_llm_analysis=False,
    )

    assert result1.transcripts_seen == 1
    assert result1.transcripts_imported == 1
    assert result1.speaker_profiles_created == 2
    assert result1.speaker_stats_imported == 1
    assert result1.transcript_stats_imported == 1

    # Group should be created.
    groups = session.query(Group).all()
    assert len(groups) == 1
    assert groups[0].slug == "default"

    # Speaker profiles should exist for each diarization label.
    profiles = session.query(SpeakerProfile).all()
    slugs = {p.slug for p in profiles}
    assert "speaker-00" in slugs
    assert "speaker-01" in slugs

    # Transcript should exist and have mappings set.
    transcripts = session.query(Transcript).all()
    assert len(transcripts) == 1
    transcript_id = transcripts[0].id

    mappings = (
        session.query(SpeakerMapping)
        .filter(SpeakerMapping.transcript_id == transcript_id)
        .all()
    )
    assert len(mappings) == 2
    assert all(m.speaker_profile_id is not None for m in mappings)

    # Stats rows should have been inserted.
    tss = (
        session.query(TranscriptSpeakerStats)
        .filter(TranscriptSpeakerStats.transcript_id == transcript_id)
        .all()
    )
    assert len(tss) == 2

    # Stat definitions should have been seeded (core+extended groups).
    stat_groups = session.query(SpeakerStatGroup).all()
    assert len(stat_groups) >= 1

    # Idempotency: re-run should not create new transcripts/speakers.
    result2 = upload_local_data_to_db(
        data_root=data_root,
        session=session,
        seed_stat_definitions=True,
        import_llm_analysis=False,
    )

    assert result2.transcripts_seen == 1
    assert result2.transcripts_imported == 0
    assert result2.speaker_profiles_created == 0

    transcripts_after = session.query(Transcript).all()
    assert len(transcripts_after) == 1
    profiles_after = session.query(SpeakerProfile).all()
    assert len(profiles_after) == 2

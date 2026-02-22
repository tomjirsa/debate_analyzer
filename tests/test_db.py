"""Tests for the web app database layer."""

import pytest
from debate_analyzer.db import Base, TranscriptRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def session():
    """In-memory SQLite session; single engine so tables persist."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def repo(session):
    """Repository using the test session."""
    return TranscriptRepository(session)


def test_create_speaker_profile(repo):
    """Creating a speaker profile persists and returns it."""
    profile = repo.create_speaker_profile(
        "Alice", "Smith", slug="alice", bio="Test bio", short_description="Short"
    )
    assert profile.id
    assert profile.first_name == "Alice"
    assert profile.surname == "Smith"
    assert profile.slug == "alice"
    assert profile.bio == "Test bio"
    assert profile.short_description == "Short"


def test_create_transcript_from_payload(repo):
    """Creating a transcript from payload creates transcript, segments, and mappings."""
    payload = {
        "duration": 100.0,
        "video_path": "/tmp/video.mp4",
        "speakers_count": 2,
        "transcription": [
            {
                "start": 0,
                "end": 5,
                "text": "Hello",
                "speaker": "SPEAKER_00",
                "confidence": 0.9,
            },
            {
                "start": 5,
                "end": 10,
                "text": "Hi",
                "speaker": "SPEAKER_01",
                "confidence": 0.95,
            },
        ],
    }
    t = repo.create_transcript_from_payload("s3://bucket/key.json", payload)
    assert t.id
    assert t.source_uri == "s3://bucket/key.json"
    assert t.duration == 100.0
    assert len(t.segments) == 2
    assert len(t.speaker_mappings) == 2
    speaker_ids = {m.speaker_id_in_transcript for m in t.speaker_mappings}
    assert speaker_ids == {"SPEAKER_00", "SPEAKER_01"}


def test_idempotent_register(repo):
    """Registering the same source_uri twice returns the same transcript."""
    payload = {
        "duration": 1.0,
        "transcription": [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}],
    }
    t1 = repo.create_transcript_from_payload("s3://b/k.json", payload)
    t2 = repo.create_transcript_from_payload("s3://b/k.json", payload)
    assert t1.id == t2.id


def test_save_mapping(repo):
    """Saving a mapping updates the speaker_profile_id."""
    payload = {
        "duration": 1.0,
        "transcription": [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}],
    }
    t = repo.create_transcript_from_payload("s3://b/k.json", payload)
    profile = repo.create_speaker_profile("Bob", "Jones")
    mapping = repo.save_mapping(t.id, "SPEAKER_00", profile.id)
    assert mapping.speaker_profile_id == profile.id
    mappings = repo.get_mappings_for_transcript(t.id)
    assert len(mappings) == 1
    assert mappings[0].speaker_profile_id == profile.id


def test_get_speaker_stats(repo):
    """Speaker stats aggregate segments for mapped profile."""
    payload = {
        "duration": 10.0,
        "transcription": [
            {"start": 0, "end": 3, "text": "one two three", "speaker": "SPEAKER_00"},
            {"start": 3, "end": 6, "text": "four five", "speaker": "SPEAKER_00"},
        ],
    }
    t = repo.create_transcript_from_payload("s3://b/k.json", payload)
    profile = repo.create_speaker_profile("Alice", "Smith")
    repo.save_mapping(t.id, "SPEAKER_00", profile.id)
    stats = repo.get_speaker_stats(profile.id)
    assert stats["total_seconds"] == 6.0
    assert stats["segment_count"] == 2
    assert stats["transcript_count"] == 1
    assert stats["word_count"] == 5
    assert stats["wpm"] == 50.0  # 5 words / (6/60) min
    assert stats["avg_segment_duration_sec"] == 3.0


def test_get_speaker_stats_includes_extended_from_transcript_stats(repo):
    """When transcript_speaker_stats has extended fields, get_speaker_stats aggregates them."""
    payload = {
        "duration": 100.0,
        "transcription": [
            {"start": 0, "end": 10, "text": "one two", "speaker": "SPEAKER_00"},
            {"start": 10, "end": 20, "text": "three four five", "speaker": "SPEAKER_00"},
        ],
    }
    t = repo.create_transcript_from_payload("s3://b/k.json", payload)
    profile = repo.create_speaker_profile("Alice", "Smith")
    repo.save_mapping(t.id, "SPEAKER_00", profile.id)
    repo.save_transcript_speaker_stats(
        t.id,
        [
            {
                "speaker_id_in_transcript": "SPEAKER_00",
                "total_seconds": 20.0,
                "segment_count": 2,
                "word_count": 5,
                "wpm": 15.0,
                "avg_segment_duration_sec": 10.0,
                "shortest_talk_sec": 8.0,
                "longest_talk_sec": 12.0,
                "median_segment_duration_sec": 10.0,
                "turn_count": 2,
                "avg_turn_length_sec": 10.0,
                "avg_turn_length_segments": 1.0,
                "is_first_speaker": True,
                "is_last_speaker": False,
                "share_speaking_time": 0.2,
                "share_words": 0.25,
            },
        ],
    )
    stats = repo.get_speaker_stats(profile.id)
    assert stats["shortest_talk_sec"] == 8.0
    assert stats["longest_talk_sec"] == 12.0
    assert stats["turn_count"] == 2
    assert stats["share_speaking_time"] == 0.2
    assert stats["share_words"] == 0.25
    assert stats["is_first_speaker"] is True
    assert stats["is_last_speaker"] is False


def test_update_speaker_profile(repo):
    """Updating a speaker profile changes fields."""
    profile = repo.create_speaker_profile("Alice", "Smith", slug="alice")
    assert profile.first_name == "Alice"
    updated = repo.update_speaker_profile(
        profile.id, first_name="Alicia", short_description="Updated"
    )
    assert updated is not None
    assert updated.first_name == "Alicia"
    assert updated.surname == "Smith"
    assert updated.short_description == "Updated"
    # None means "do not change"
    repo.update_speaker_profile(profile.id, bio="New bio")
    refreshed = repo.get_speaker_profile_by_id(profile.id)
    assert refreshed.bio == "New bio"
    assert refreshed.first_name == "Alicia"


def test_delete_speaker_profile(repo):
    """Deleting a speaker profile removes it and returns True."""
    profile = repo.create_speaker_profile("Bob", "Jones")
    assert repo.get_speaker_profile_by_id(profile.id) is not None
    assert repo.delete_speaker_profile(profile.id) is True
    assert repo.get_speaker_profile_by_id(profile.id) is None
    assert repo.delete_speaker_profile(profile.id) is False


def test_save_and_get_speaker_stats_for_transcript(repo):
    """Save and get transcript speaker stats returns same data (incl. extended)."""
    payload = {
        "duration": 10.0,
        "transcription": [
            {"start": 0, "end": 5, "text": "one two three", "speaker": "SPEAKER_00"},
            {"start": 5, "end": 10, "text": "four five six", "speaker": "SPEAKER_01"},
        ],
    }
    t = repo.create_transcript_from_payload("s3://b/k.json", payload)
    rows = [
        {
            "speaker_id_in_transcript": "SPEAKER_00",
            "total_seconds": 5.0,
            "segment_count": 1,
            "word_count": 3,
            "wpm": 36.0,
            "turn_count": 1,
            "is_first_speaker": True,
            "share_speaking_time": 0.5,
            "share_words": 0.5,
        },
        {
            "speaker_id_in_transcript": "SPEAKER_01",
            "total_seconds": 5.0,
            "segment_count": 1,
            "word_count": 3,
            "wpm": 36.0,
            "turn_count": 1,
            "is_first_speaker": False,
            "is_last_speaker": True,
            "share_speaking_time": 0.5,
            "share_words": 0.5,
        },
    ]
    repo.save_transcript_speaker_stats(t.id, rows)
    got = repo.get_speaker_stats_for_transcript(t.id)
    assert len(got) == 2
    by_speaker = {r["speaker_id_in_transcript"]: r for r in got}
    assert by_speaker["SPEAKER_00"]["total_seconds"] == 5.0
    assert by_speaker["SPEAKER_00"]["word_count"] == 3
    assert by_speaker["SPEAKER_00"]["wpm"] == 36.0
    assert by_speaker["SPEAKER_00"]["turn_count"] == 1
    assert by_speaker["SPEAKER_00"]["is_first_speaker"] is True
    assert by_speaker["SPEAKER_01"]["segment_count"] == 1
    assert by_speaker["SPEAKER_01"]["is_last_speaker"] is True


def test_save_transcript_speaker_stats_idempotent(repo):
    """Re-saving stats for the same transcript replaces existing rows."""
    payload = {
        "duration": 1.0,
        "transcription": [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}],
    }
    t = repo.create_transcript_from_payload("s3://b/k.json", payload)
    repo.save_transcript_speaker_stats(
        t.id,
        [
            {
                "speaker_id_in_transcript": "SPEAKER_00",
                "total_seconds": 1.0,
                "segment_count": 1,
                "word_count": 1,
            }
        ],
    )
    repo.save_transcript_speaker_stats(
        t.id,
        [
            {
                "speaker_id_in_transcript": "SPEAKER_00",
                "total_seconds": 2.0,
                "segment_count": 2,
                "word_count": 2,
            }
        ],
    )
    got = repo.get_speaker_stats_for_transcript(t.id)
    assert len(got) == 1
    assert got[0]["total_seconds"] == 2.0
    assert got[0]["word_count"] == 2


def test_get_speaker_stats_by_transcript(repo):
    """Per-transcript breakdown joins stats with mapping and transcript."""
    payload1 = {
        "duration": 10.0,
        "transcription": [
            {"start": 0, "end": 10, "text": "a b c", "speaker": "SPEAKER_00"}
        ],
    }
    payload2 = {
        "duration": 5.0,
        "transcription": [
            {"start": 0, "end": 5, "text": "x y", "speaker": "SPEAKER_00"}
        ],
    }
    t1 = repo.create_transcript_from_payload(
        "s3://b/t1.json", payload1, title="Transcript A"
    )
    t2 = repo.create_transcript_from_payload(
        "s3://b/t2.json", payload2, title="Transcript B"
    )
    profile = repo.create_speaker_profile("Alice", "Smith")
    repo.save_mapping(t1.id, "SPEAKER_00", profile.id)
    repo.save_mapping(t2.id, "SPEAKER_00", profile.id)
    repo.save_transcript_speaker_stats(
        t1.id,
        [
            {
                "speaker_id_in_transcript": "SPEAKER_00",
                "total_seconds": 10.0,
                "segment_count": 1,
                "word_count": 3,
            }
        ],
    )
    repo.save_transcript_speaker_stats(
        t2.id,
        [
            {
                "speaker_id_in_transcript": "SPEAKER_00",
                "total_seconds": 5.0,
                "segment_count": 1,
                "word_count": 2,
            }
        ],
    )
    breakdown = repo.get_speaker_stats_by_transcript(profile.id)
    assert len(breakdown) == 2
    titles = {r["transcript_title"]: r for r in breakdown}
    assert "Transcript A" in titles
    assert "Transcript B" in titles
    assert titles["Transcript A"]["total_seconds"] == 10.0
    assert titles["Transcript B"]["word_count"] == 2


def test_get_stat_definitions(repo):
    """Stat definitions returns groups with their stats in correct structure."""
    from debate_analyzer.db.models import SpeakerStatDefinition, SpeakerStatGroup

    group = SpeakerStatGroup(key="test_group", label="Test", sort_order=0)
    repo.session.add(group)
    repo.session.flush()
    repo.session.add(
        SpeakerStatDefinition(
            stat_key="total_seconds", group_id=group.id, label="Total sec", sort_order=0
        )
    )
    repo.session.commit()
    groups = repo.get_stat_definitions()
    assert len(groups) >= 1
    test_group = next((g for g in groups if g["key"] == "test_group"), None)
    assert test_group is not None
    assert test_group["label"] == "Test"
    assert "stats" in test_group
    assert len(test_group["stats"]) == 1
    assert test_group["stats"][0]["stat_key"] == "total_seconds"
    assert test_group["stats"][0]["label"] == "Total sec"

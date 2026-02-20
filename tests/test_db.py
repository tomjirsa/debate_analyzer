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

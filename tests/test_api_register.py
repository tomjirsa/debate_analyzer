"""Tests for transcript registration API including LLM analysis auto-import."""

import json
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from debate_analyzer.api.app import app
from debate_analyzer.api.auth import get_admin_credentials
from debate_analyzer.db import Base, TranscriptRepository
from debate_analyzer.db.base import get_db
from debate_analyzer.db.models import (  # ensure all models registered with Base
    Group,
    Segment,
    SpeakerMapping,
    SpeakerProfile,
    SpeakerStatDefinition,
    SpeakerStatGroup,
    Transcript,
    TranscriptLLMAnalysis,
    TranscriptSpeakerStats,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Single in-memory DB session for API tests; shared so request thread sees tables."""
    engine = create_engine(
        "sqlite:///file:memdb?mode=memory&cache=shared",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session):
    """TestClient with DB and admin auth overrides."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_admin_credentials():
        return None  # any value; we only need to pass the dependency

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_admin_credentials] = override_get_admin_credentials
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_admin_credentials, None)


@pytest.fixture
def default_group(db_session: Session):
    """Create a group in the DB so we have a group_id for register; unique slug per test."""
    repo = TranscriptRepository(db_session)
    slug = f"test-{uuid.uuid4().hex[:8]}"
    group = repo.create_group("Test Group", slug, description="For tests")
    db_session.commit()
    return group.to_dict()


def _minimal_transcription_payload():
    return {
        "duration": 60.0,
        "video_path": "/tmp/v.mp4",
        "speakers_count": 1,
        "transcription": [
            {"start": 0, "end": 5, "text": "Hello", "speaker": "SPEAKER_00"},
        ],
    }


def _valid_analysis_result():
    return {
        "main_topics": [{"id": "t1", "title": "Topic A", "description": "Desc"}],
        "topic_summaries": [{"topic_id": "t1", "summary": "Summary text"}],
        "speaker_contributions": [],
    }


def test_register_returns_transcript_in_response(client, default_group, tmp_path):
    """Register response has consistent shape with 'transcript' key; no warning when URI has no _transcription.json."""
    transcript_file = tmp_path / "foo.json"
    transcript_file.write_text(
        json.dumps(_minimal_transcription_payload()), encoding="utf-8"
    )
    uri = f"file://{transcript_file}"
    r = client.post(
        "/api/admin/transcripts/register",
        json={
            "source_uri": uri,
            "title": "Test",
            "group_id": default_group["id"],
        },
        auth=("admin", "admin"),
    )
    if r.status_code == 401:
        pytest.skip("Admin auth required")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transcript" in data
    assert data["transcript"]["title"] == "Test"
    assert data["transcript"]["id"]
    assert "warning" not in data


def test_register_with_llm_analysis_imports_and_no_warning(
    client, default_group, tmp_path
):
    """When _llm_analysis.json exists and is valid, analysis is attached and no warning."""
    transcript_file = tmp_path / "bar_transcription.json"
    transcript_file.write_text(
        json.dumps(_minimal_transcription_payload()), encoding="utf-8"
    )
    analysis_file = tmp_path / "bar_llm_analysis.json"
    analysis_file.write_text(
        json.dumps(_valid_analysis_result(), ensure_ascii=False),
        encoding="utf-8",
    )
    uri = f"file://{transcript_file}"
    r = client.post(
        "/api/admin/transcripts/register",
        json={
            "source_uri": uri,
            "title": "With analysis",
            "group_id": default_group["id"],
        },
        auth=("admin", "admin"),
    )
    if r.status_code == 401:
        pytest.skip("Admin auth required")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transcript" in data
    assert "warning" not in data
    tid = data["transcript"]["id"]
    get_r = client.get(
        f"/api/admin/transcripts/{tid}/analysis",
        auth=("admin", "admin"),
    )
    assert get_r.status_code == 200, get_r.text
    analysis = get_r.json()
    assert "result" in analysis
    assert analysis["result"]["main_topics"]


def test_register_without_llm_analysis_file_returns_warning(
    client, default_group, tmp_path
):
    """When _transcription.json is used but _llm_analysis.json is missing, response has warning."""
    transcript_file = tmp_path / "baz_transcription.json"
    transcript_file.write_text(
        json.dumps(_minimal_transcription_payload()), encoding="utf-8"
    )
    uri = f"file://{transcript_file}"
    r = client.post(
        "/api/admin/transcripts/register",
        json={
            "source_uri": uri,
            "title": "No analysis file",
            "group_id": default_group["id"],
        },
        auth=("admin", "admin"),
    )
    if r.status_code == 401:
        pytest.skip("Admin auth required")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transcript" in data
    assert "warning" in data
    assert "LLM analysis not imported" in data["warning"]
    assert "not found" in data["warning"].lower() or "file" in data["warning"].lower()


def test_register_with_invalid_llm_analysis_returns_warning(
    client, default_group, tmp_path
):
    """When _llm_analysis.json exists but lacks main_topics, response has warning."""
    transcript_file = tmp_path / "qux_transcription.json"
    transcript_file.write_text(
        json.dumps(_minimal_transcription_payload()), encoding="utf-8"
    )
    analysis_file = tmp_path / "qux_llm_analysis.json"
    analysis_file.write_text(json.dumps({"topic_summaries": []}), encoding="utf-8")
    uri = f"file://{transcript_file}"
    r = client.post(
        "/api/admin/transcripts/register",
        json={
            "source_uri": uri,
            "title": "Bad analysis",
            "group_id": default_group["id"],
        },
        auth=("admin", "admin"),
    )
    if r.status_code == 401:
        pytest.skip("Admin auth required")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transcript" in data
    assert "warning" in data
    assert "LLM analysis not imported" in data["warning"]


def test_register_uri_without_transcription_suffix_no_warning(client, default_group, tmp_path):
    """When source_uri does not contain _transcription.json, no analysis attempt and no warning."""
    other_file = tmp_path / "other.json"
    other_file.write_text(
        json.dumps(_minimal_transcription_payload()), encoding="utf-8"
    )
    uri = f"file://{other_file}"
    r = client.post(
        "/api/admin/transcripts/register",
        json={
            "source_uri": uri,
            "title": "Other URI",
            "group_id": default_group["id"],
        },
        auth=("admin", "admin"),
    )
    if r.status_code == 401:
        pytest.skip("Admin auth required")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transcript" in data
    assert "warning" not in data

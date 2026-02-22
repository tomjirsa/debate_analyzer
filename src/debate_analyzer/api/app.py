"""FastAPI application: public and admin API, static files."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from debate_analyzer.api.auth import get_admin_credentials
from debate_analyzer.api.loader import (
    load_speaker_stats_parquet,
    load_transcript_payload,
)
from debate_analyzer.api.s3_utils import generate_presigned_get_url, parse_s3_uri
from debate_analyzer.db import TranscriptRepository, init_db
from debate_analyzer.db.base import get_db

app = FastAPI(title="Debate Analyzer Web", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    """Ensure DB tables exist on startup."""
    init_db()


def get_repo_from_db(db: Annotated[Session, Depends(get_db)]) -> TranscriptRepository:
    """Dependency: repository from request-scoped DB session."""
    return TranscriptRepository(db)


# ---------- Public API (no auth) ----------


@app.get("/api/speakers")
def list_speakers(
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> list[dict]:
    """List all speaker profiles (public)."""
    return [p.to_dict() for p in repo.list_speaker_profiles()]


@app.get("/api/speakers/{id_or_slug}")
def get_speaker(
    id_or_slug: str,
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Get speaker profile and stats by id or slug (public)."""
    profile = repo.get_speaker_profile_by_id(
        id_or_slug
    ) or repo.get_speaker_profile_by_slug(id_or_slug)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    stats = repo.get_speaker_stats(profile.id)
    stats_by_transcript = repo.get_speaker_stats_by_transcript(profile.id)
    return {
        "profile": profile.to_dict(),
        "stats": stats,
        "stats_by_transcript": stats_by_transcript,
    }


@app.get("/api/stat-definitions")
def get_stat_definitions(
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> list[dict]:
    """Return stat groups with stat definitions for grouped UI display (public)."""
    return repo.get_stat_definitions()


# ---------- Admin API (basic auth) ----------


@app.get("/api/admin/transcripts")
def admin_list_transcripts(
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List transcripts (admin)."""
    return [t.to_dict() for t in repo.list_transcripts(limit=limit, offset=offset)]


@app.get("/api/admin/transcripts/{transcript_id}")
def admin_get_transcript(
    transcript_id: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Get transcript with segments and current speaker mappings (admin)."""
    transcript = repo.get_transcript_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    mappings = repo.get_mappings_for_transcript(transcript_id)
    segments = [
        {
            "id": s.id,
            "start": s.start,
            "end": s.end,
            "text": s.text,
            "speaker_id_in_transcript": s.speaker_id_in_transcript,
            "confidence": s.confidence,
        }
        for s in transcript.segments
    ]
    speaker_stats = repo.get_speaker_stats_for_transcript(transcript_id)
    return {
        "transcript": transcript.to_dict(),
        "mappings": [m.to_dict() for m in mappings],
        "segments": segments,
        "speaker_stats": speaker_stats,
    }


class RegisterTranscriptRequest(BaseModel):
    """Request body for register transcript."""

    source_uri: str
    title: str | None = None


@app.post("/api/admin/transcripts/register")
def admin_register_transcript(
    body: RegisterTranscriptRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Register transcript from S3 or file; creates transcript, segments, mappings."""
    try:
        payload = load_transcript_payload(body.source_uri)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    source_type = "s3" if body.source_uri.strip().startswith("s3://") else "file"
    transcript = repo.create_transcript_from_payload(
        body.source_uri,
        payload,
        source_type=source_type,
        title=body.title,
    )
    if "_transcription.json" in body.source_uri:
        parquet_uri = body.source_uri.replace(
            "_transcription.json", "_speaker_stats.parquet"
        )
        stats_rows = load_speaker_stats_parquet(parquet_uri)
        if stats_rows:
            repo.save_transcript_speaker_stats(transcript.id, stats_rows)
    return transcript.to_dict()


class UpdateTranscriptRequest(BaseModel):
    """Request body for update transcript (all fields optional)."""

    title: str | None = None
    video_path: str | None = None


@app.put("/api/admin/transcripts/{transcript_id}")
def admin_update_transcript(
    transcript_id: str,
    body: UpdateTranscriptRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Update transcript title and/or video_path (admin)."""
    transcript = repo.update_transcript(
        transcript_id,
        title=body.title,
        video_path=body.video_path,
    )
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
        )
    return transcript.to_dict()


@app.delete("/api/admin/transcripts/{transcript_id}")
def admin_delete_transcript(
    transcript_id: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> Response:
    """Delete transcript and its segments/mappings (admin)."""
    if not repo.delete_transcript(transcript_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class CreateSpeakerRequest(BaseModel):
    """Request body for create speaker."""

    first_name: str
    surname: str
    slug: str | None = None
    bio: str | None = None
    short_description: str | None = None


class UpdateSpeakerRequest(BaseModel):
    """Request body for update speaker (all fields optional)."""

    first_name: str | None = None
    surname: str | None = None
    slug: str | None = None
    bio: str | None = None
    short_description: str | None = None


@app.post("/api/admin/speakers")
def admin_create_speaker(
    body: CreateSpeakerRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Create a speaker profile (admin)."""
    profile = repo.create_speaker_profile(
        first_name=body.first_name,
        surname=body.surname,
        slug=body.slug,
        bio=body.bio,
        short_description=body.short_description,
    )
    return profile.to_dict()


@app.put("/api/admin/speakers/{profile_id}")
def admin_update_speaker(
    profile_id: str,
    body: UpdateSpeakerRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Update a speaker profile (admin)."""
    profile = repo.update_speaker_profile(
        profile_id,
        first_name=body.first_name,
        surname=body.surname,
        slug=body.slug,
        bio=body.bio,
        short_description=body.short_description,
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    return profile.to_dict()


@app.delete("/api/admin/speakers/{profile_id}")
def admin_delete_speaker(
    profile_id: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> Response:
    """Delete a speaker profile (admin). Mappings are CASCADE-deleted."""
    if not repo.delete_speaker_profile(profile_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class SaveMappingsRequest(BaseModel):
    """Request body: map speaker_id_in_transcript -> speaker_profile_id (or null)."""

    mappings: dict[str, str | None]


@app.put("/api/admin/transcripts/{transcript_id}/mappings")
def admin_save_mappings(
    transcript_id: str,
    body: SaveMappingsRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Save speaker mappings for a transcript (admin)."""
    transcript = repo.get_transcript_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    repo.save_mappings_bulk(transcript_id, body.mappings)
    return {"ok": True}


VIDEO_URL_EXPIRES_IN = 3600


@app.get("/api/admin/transcripts/{transcript_id}/video-url")
def admin_transcript_video_url(
    transcript_id: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
    s3_uri: str | None = None,
) -> dict:
    """
    Return a presigned GET URL for the transcript's video (admin).

    If s3_uri is provided, presign that URI. Otherwise use the transcript's
    video_path only when it starts with s3://.
    """
    transcript = repo.get_transcript_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    uri_to_use = s3_uri and s3_uri.strip() or None
    if (
        not uri_to_use
        and transcript.video_path
        and transcript.video_path.strip().startswith("s3://")
    ):
        uri_to_use = transcript.video_path.strip()

    if not uri_to_use or not uri_to_use.startswith("s3://"):
        raise HTTPException(
            status_code=400,
            detail=(
                "No S3 video URI. Use s3_uri query or set transcript video_path to s3://."
            ),
        )

    try:
        bucket, key = parse_s3_uri(uri_to_use)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    url = generate_presigned_get_url(bucket, key, expires_in=VIDEO_URL_EXPIRES_IN)
    return {"url": url, "expires_in": VIDEO_URL_EXPIRES_IN}


@app.get("/api/admin/speakers")
def admin_list_speakers(
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> list[dict]:
    """List all speaker profiles (admin). Same as public list but behind auth."""
    return [p.to_dict() for p in repo.list_speaker_profiles()]


# ---------- Static / UI (Vue SPA) ----------


STATIC_DIR = Path(__file__).parent / "static"

# Serve Vue build assets (JS, CSS with hashed filenames).
if (STATIC_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/{full_path:path}", response_model=None)
def serve_spa(full_path: str) -> FileResponse | dict:
    """
    Catch-all: serve index.html for SPA client-side routes.
    Skip paths that belong to API or docs (should not reach here if defined above).
    """
    if (
        full_path.startswith("api/")
        or full_path == "api"
        or full_path == "docs"
        or full_path == "openapi.json"
        or full_path.startswith("assets/")
    ):
        raise HTTPException(status_code=404, detail="Not found")
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, headers={"Cache-Control": "no-store"})
    return {"message": "Debate Analyzer API", "docs": "/docs", "api": "/api/speakers"}

"""FastAPI application: public and admin API, static files."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from debate_analyzer.api.auth import get_admin_credentials
from debate_analyzer.api.loader import load_transcript_payload
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
    return {"profile": profile.to_dict(), "stats": stats}


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
    return {
        "transcript": transcript.to_dict(),
        "mappings": [m.to_dict() for m in mappings],
        "segments": segments,
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
    return transcript.to_dict()


class CreateSpeakerRequest(BaseModel):
    """Request body for create speaker."""

    display_name: str
    slug: str | None = None
    bio: str | None = None


@app.post("/api/admin/speakers")
def admin_create_speaker(
    body: CreateSpeakerRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Create a speaker profile (admin)."""
    profile = repo.create_speaker_profile(
        display_name=body.display_name,
        slug=body.slug,
        bio=body.bio,
    )
    return profile.to_dict()


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
    if not uri_to_use and transcript.video_path and transcript.video_path.strip().startswith("s3://"):
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


# ---------- Static / UI ----------


STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_model=None)
def index() -> FileResponse | dict:
    """Serve public index (speaker list) or JSON if static not present."""
    for name in ("index.html", "public/index.html"):
        p = STATIC_DIR / name
        if p.exists():
            return FileResponse(p)
    return {"message": "Debate Analyzer API", "docs": "/docs", "api": "/api/speakers"}


@app.get("/speakers/{id_or_slug:path}", response_model=None)
def speaker_page(id_or_slug: str) -> FileResponse:
    """Serve speaker detail page (public)."""
    p = STATIC_DIR / "public" / "speaker.html"
    if p.exists():
        return FileResponse(p)
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/admin", response_model=None)
def admin_index() -> FileResponse | dict:
    """Serve admin UI or message if static not present."""
    for name in ("admin/index.html", "admin.html"):
        p = STATIC_DIR / name
        if p.exists():
            return FileResponse(p)
    return {
        "message": "Admin API",
        "docs": "/docs",
        "admin_transcripts": "/api/admin/transcripts",
    }


@app.get("/admin/annotate", response_model=None)
def admin_annotate_page() -> FileResponse:
    """Serve speaker annotation page (admin)."""
    p = STATIC_DIR / "admin" / "annotate.html"
    if p.exists():
        return FileResponse(p)
    raise HTTPException(status_code=404, detail="Not found")

"""FastAPI application: public and admin API, static files."""

import os
from datetime import date
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
    load_transcript_stats_json,
)
from debate_analyzer.api.s3_utils import (
    generate_presigned_get_url,
    generate_presigned_put_url,
    parse_s3_uri,
)
from debate_analyzer.db import SpeakerProfile, TranscriptRepository, init_db
from debate_analyzer.db.base import get_db

app = FastAPI(title="Debate Analyzer Web", version="0.1.0")

# Allowed extension and Content-Type for speaker photo uploads
SPEAKER_PHOTO_EXT_ALLOWLIST = {"jpg", "jpeg", "png", "webp"}
SPEAKER_PHOTO_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


# Expiry for presigned GET URLs when SPEAKER_PHOTOS_BASE_URL is not set (fallback)
SPEAKER_PHOTO_PRESIGNED_GET_EXPIRES_IN = 3600


def _speaker_to_dict(profile: SpeakerProfile) -> dict:
    """Serialize speaker profile to dict and add photo_url from config."""
    d = profile.to_dict()
    base = os.environ.get("SPEAKER_PHOTOS_BASE_URL", "").strip()
    bucket = os.environ.get("SPEAKER_PHOTOS_S3_BUCKET", "").strip()
    key_strip = (profile.photo_key or "").strip().lstrip("/")

    if not key_strip:
        d["photo_url"] = None
        return d

    if base:
        base_rstrip = base.rstrip("/")
        d["photo_url"] = f"{base_rstrip}/{key_strip}"
    elif bucket:
        try:
            d["photo_url"] = generate_presigned_get_url(
                bucket=bucket,
                key=key_strip,
                expires_in=SPEAKER_PHOTO_PRESIGNED_GET_EXPIRES_IN,
            )
        except Exception:
            d["photo_url"] = None
    else:
        d["photo_url"] = None
    return d


@app.on_event("startup")
def startup() -> None:
    """Ensure DB tables exist on startup."""
    init_db()


def get_repo_from_db(db: Annotated[Session, Depends(get_db)]) -> TranscriptRepository:
    """Dependency: repository from request-scoped DB session."""
    return TranscriptRepository(db)


# ---------- Public API (no auth) ----------


@app.get("/api/groups")
def list_groups(
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> list[dict]:
    """List all content groups (public, for dashboard switcher)."""
    return [g.to_dict() for g in repo.list_groups()]


@app.get("/api/groups/{group_id_or_slug}")
def get_group(
    group_id_or_slug: str,
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Get a single group by id or slug (public)."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return group.to_dict()


def _default_group_id(repo: TranscriptRepository) -> str | None:
    """Return default group id if it exists."""
    g = repo.get_group_by_slug("default")
    return g.id if g else None


@app.get("/api/groups/{group_id_or_slug}/speakers")
def list_speakers_in_group(
    group_id_or_slug: str,
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> list[dict]:
    """List speaker profiles in a group (public). Includes transcript_count per speaker."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    profiles = repo.list_speaker_profiles(group_id=group.id)
    profile_ids = [p.id for p in profiles]
    counts = repo.get_transcript_counts_for_speakers(profile_ids)
    return [
        {**_speaker_to_dict(p), "transcript_count": counts.get(p.id, 0)}
        for p in profiles
    ]


@app.get("/api/groups/{group_id_or_slug}/transcripts")
def list_transcripts_in_group(
    group_id_or_slug: str,
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
    limit: int = 50,
) -> list[dict]:
    """List transcripts in a group (public). Returns minimal fields for dashboard."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    transcripts = repo.list_transcripts(limit=limit, group_id=group.id)
    return [t.to_dict() for t in transcripts]


@app.get("/api/groups/{group_id_or_slug}/transcripts/{transcript_id}")
def get_transcript_in_group(
    group_id_or_slug: str,
    transcript_id: str,
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Get transcript and per-speaker stats by id within a group (public)."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    transcript = repo.get_transcript_by_id(transcript_id, group_id=group.id)
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
        )
    speaker_stats = repo.get_speaker_stats_for_transcript(transcript_id)
    response: dict = {
        "transcript": transcript.to_dict(),
        "speaker_stats": speaker_stats,
    }
    analysis = repo.get_latest_llm_analysis(transcript_id)
    if analysis:
        response["llm_analysis"] = analysis.result
    return response


@app.get("/api/groups/{group_id_or_slug}/speakers/{id_or_slug}")
def get_speaker_in_group(
    group_id_or_slug: str,
    id_or_slug: str,
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Get speaker profile and stats by id or slug within a group (public)."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    profile = repo.get_speaker_profile_by_id(
        id_or_slug, group_id=group.id
    ) or repo.get_speaker_profile_by_slug(id_or_slug, group_id=group.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    stats = repo.get_speaker_stats(profile.id)
    stats_by_transcript = repo.get_speaker_stats_by_transcript(profile.id)
    return {
        "profile": _speaker_to_dict(profile),
        "stats": stats,
        "stats_by_transcript": stats_by_transcript,
    }


@app.get("/api/speakers")
def list_speakers(
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
    group_id: str | None = None,
) -> list[dict]:
    """List speaker profiles (public). Optional group_id to filter by group."""
    return [_speaker_to_dict(p) for p in repo.list_speaker_profiles(group_id=group_id)]


@app.get("/api/speakers/{id_or_slug}")
def get_speaker(
    id_or_slug: str,
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
    group_id: str | None = None,
) -> dict:
    """Get speaker profile and stats by id or slug (public). For slug lookup, group_id or default group is used."""
    profile = repo.get_speaker_profile_by_id(id_or_slug, group_id=group_id)
    if not profile and not group_id:
        default_id = _default_group_id(repo)
        if default_id:
            profile = repo.get_speaker_profile_by_slug(id_or_slug, group_id=default_id)
    if not profile and group_id:
        profile = repo.get_speaker_profile_by_slug(id_or_slug, group_id=group_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    stats = repo.get_speaker_stats(profile.id)
    stats_by_transcript = repo.get_speaker_stats_by_transcript(profile.id)
    return {
        "profile": _speaker_to_dict(profile),
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


# ----- Admin: Groups -----


class CreateGroupRequest(BaseModel):
    """Request body for create group."""

    name: str
    slug: str
    description: str | None = None


class UpdateGroupRequest(BaseModel):
    """Request body for update group (all fields optional)."""

    name: str | None = None
    slug: str | None = None
    description: str | None = None


@app.get("/api/admin/groups")
def admin_list_groups(
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> list[dict]:
    """List all groups (admin)."""
    return [g.to_dict() for g in repo.list_groups()]


@app.post("/api/admin/groups")
def admin_create_group(
    body: CreateGroupRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Create a content group (admin)."""
    group = repo.create_group(
        name=body.name,
        slug=body.slug,
        description=body.description,
    )
    return group.to_dict()


@app.get("/api/admin/groups/{group_id_or_slug}")
def admin_get_group(
    group_id_or_slug: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Get group by id or slug (admin)."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    return group.to_dict()


@app.put("/api/admin/groups/{group_id_or_slug}")
def admin_update_group(
    group_id_or_slug: str,
    body: UpdateGroupRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Update group (admin)."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    updated = repo.update_group(
        group.id,
        name=body.name,
        slug=body.slug,
        description=body.description,
    )
    return updated.to_dict()


@app.delete("/api/admin/groups/{group_id_or_slug}")
def admin_delete_group(
    group_id_or_slug: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> Response:
    """Delete group (admin). Fails if group has transcripts or speakers."""
    group = repo.get_group_by_id(group_id_or_slug) or repo.get_group_by_slug(
        group_id_or_slug
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )
    if not repo.delete_group(group.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete group with transcripts or speakers",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- Admin: Transcripts -----


@app.get("/api/admin/transcripts")
def admin_list_transcripts(
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
    limit: int = 100,
    offset: int = 0,
    group_id: str | None = None,
) -> list[dict]:
    """List transcripts (admin). Optional group_id to filter."""
    return [
        t.to_dict()
        for t in repo.list_transcripts(limit=limit, offset=offset, group_id=group_id)
    ]


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
    title: str
    group_id: str | None = None
    description: str | None = None
    debate_date: date | None = None
    llm_model_name: str | None = None


@app.post("/api/admin/transcripts/register")
def admin_register_transcript(
    body: RegisterTranscriptRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Register transcript from S3 or file; creates transcript, segments, mappings."""
    if not body.title or not body.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title is required.",
        )
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
        title=body.title.strip(),
        group_id=body.group_id,
        description=body.description,
        debate_date=body.debate_date,
    )
    llm_import_warning: str | None = None
    if "_transcription.json" in body.source_uri:
        parquet_uri = body.source_uri.replace(
            "_transcription.json", "_speaker_stats.parquet"
        )
        stats_rows = load_speaker_stats_parquet(parquet_uri)
        if stats_rows:
            repo.save_transcript_speaker_stats(transcript.id, stats_rows)
        stats = load_transcript_stats_json(body.source_uri)
        if stats:
            updated = repo.update_transcript_stats(transcript.id, **stats)
            if updated:
                transcript = updated

        analysis_uri = body.source_uri.replace(
            "_transcription.json", "_llm_analysis.json"
        )
        try:
            analysis_payload = load_transcript_payload(analysis_uri)
        except FileNotFoundError:
            llm_import_warning = "LLM analysis not imported: analysis file not found"
        except ValueError:
            llm_import_warning = "LLM analysis not imported: invalid analysis JSON"
        else:
            result = (
                analysis_payload.get("result", analysis_payload)
                if isinstance(analysis_payload.get("result"), dict)
                else analysis_payload
            )
            if not isinstance(result, dict) or "speaker_contributions" not in result:
                llm_import_warning = (
                    "LLM analysis not imported: analysis missing speaker_contributions"
                )
            else:
                repo.create_llm_analysis(
                    transcript_id=transcript.id,
                    model_name=body.llm_model_name or "batch",
                    result=result,
                    source="batch",
                )

    response: dict = {"transcript": transcript.to_dict()}
    if llm_import_warning is not None:
        response["warning"] = llm_import_warning
    return response


class UpdateTranscriptRequest(BaseModel):
    """Request body for update transcript (all fields optional)."""

    title: str | None = None
    video_path: str | None = None
    description: str | None = None
    debate_date: date | None = None


@app.put("/api/admin/transcripts/{transcript_id}")
def admin_update_transcript(
    transcript_id: str,
    body: UpdateTranscriptRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Update transcript title, video_path, description, and/or debate_date (admin)."""
    transcript = repo.update_transcript(
        transcript_id,
        title=body.title,
        video_path=body.video_path,
        description=body.description,
        debate_date=body.debate_date,
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


@app.get("/api/admin/transcripts/{transcript_id}/analysis")
def admin_get_transcript_analysis(
    transcript_id: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Get the latest LLM analysis for a transcript (admin). Returns 404 if none."""
    analysis = repo.get_latest_llm_analysis(transcript_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No LLM analysis found for this transcript",
        )
    return analysis.to_dict()


class ImportAnalysisRequest(BaseModel):
    """Request body for import LLM analysis: either source_uri or inline result."""

    source_uri: str | None = None
    result: dict | None = None
    model_name: str = "Qwen/Qwen2-1.5B-Instruct"
    source: str = "api"


@app.post("/api/admin/transcripts/{transcript_id}/analysis/import")
def admin_import_transcript_analysis(
    transcript_id: str,
    body: ImportAnalysisRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Import LLM analysis from S3/file (source_uri) or inline JSON (result) (admin)."""
    if not repo.get_transcript_by_id(transcript_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
        )
    if body.source_uri:
        try:
            payload = load_transcript_payload(body.source_uri)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        result = (
            payload.get("result", payload)
            if isinstance(payload.get("result"), dict)
            else payload
        )
        if not isinstance(result, dict) or "speaker_contributions" not in result:
            raise HTTPException(
                status_code=400,
                detail="Invalid analysis: expected object with speaker_contributions",
            )
    elif body.result is not None:
        result = body.result
        if not isinstance(result, dict) or "speaker_contributions" not in result:
            raise HTTPException(
                status_code=400,
                detail="Invalid analysis: expected object with speaker_contributions",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either source_uri or result",
        )
    analysis = repo.create_llm_analysis(
        transcript_id=transcript_id,
        model_name=body.model_name,
        result=result,
        source=body.source,
    )
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
        )
    return analysis.to_dict()


class CreateSpeakerRequest(BaseModel):
    """Request body for create speaker."""

    first_name: str
    surname: str
    group_id: str
    slug: str | None = None
    bio: str | None = None
    short_description: str | None = None
    photo_key: str | None = None


class UpdateSpeakerRequest(BaseModel):
    """Request body for update speaker (all fields optional)."""

    first_name: str | None = None
    surname: str | None = None
    slug: str | None = None
    bio: str | None = None
    short_description: str | None = None
    photo_key: str | None = None


@app.post("/api/admin/speakers")
def admin_create_speaker(
    body: CreateSpeakerRequest,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
) -> dict:
    """Create a speaker profile in the given group (admin)."""
    profile = repo.create_speaker_profile(
        first_name=body.first_name,
        surname=body.surname,
        group_id=body.group_id,
        slug=body.slug,
        bio=body.bio,
        short_description=body.short_description,
        photo_key=body.photo_key,
    )
    return _speaker_to_dict(profile)


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
        photo_key=body.photo_key,
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    return _speaker_to_dict(profile)


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


PHOTO_UPLOAD_EXPIRES_IN = 3600


@app.get("/api/admin/speakers/{profile_id}/photo-upload-url")
def admin_speaker_photo_upload_url(
    profile_id: str,
    _: Annotated[object, Depends(get_admin_credentials)],
    repo: Annotated[TranscriptRepository, Depends(get_repo_from_db)],
    ext: str = "jpg",
) -> dict:
    """
    Return a presigned PUT URL for uploading a speaker profile photo (admin).

    Query param ext must be one of: jpg, jpeg, png, webp. The client should PUT
    the file to put_url with the corresponding Content-Type, then PATCH the
    speaker with photo_key set to the returned key.
    """
    profile = repo.get_speaker_profile_by_id(profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    ext_lower = ext.lower().lstrip(".")
    if ext_lower not in SPEAKER_PHOTO_EXT_ALLOWLIST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ext must be one of: {', '.join(sorted(SPEAKER_PHOTO_EXT_ALLOWLIST))}",
        )
    bucket = os.environ.get("SPEAKER_PHOTOS_S3_BUCKET", "").strip()
    if not bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Speaker photo upload is not configured: set SPEAKER_PHOTOS_S3_BUCKET "
                "(and optionally SPEAKER_PHOTOS_BASE_URL for stable image URLs). "
                "See doc/DEVELOPMENT.md for local testing."
            ),
        )
    key = f"speaker-photos/{profile.group_id}/{profile_id}.{ext_lower}"
    content_type = SPEAKER_PHOTO_CONTENT_TYPES.get(ext_lower)
    put_url = generate_presigned_put_url(
        bucket=bucket,
        key=key,
        expires_in=PHOTO_UPLOAD_EXPIRES_IN,
        content_type=content_type,
    )
    return {
        "put_url": put_url,
        "key": key,
        "expires_in": PHOTO_UPLOAD_EXPIRES_IN,
    }


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
    group_id: str | None = None,
) -> list[dict]:
    """List speaker profiles (admin). Optional group_id to filter."""
    return [_speaker_to_dict(p) for p in repo.list_speaker_profiles(group_id=group_id)]


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

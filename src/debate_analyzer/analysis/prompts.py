"""Prompt templates for LLM transcript analysis phases."""

from __future__ import annotations

# Phase 1: extract topic labels from a chunk. (Braces in JSON escaped for .format.)
PROMPT_TOPICS_CHUNK = """You are analyzing a transcript of a meeting or debate. \
Below is a portion of the transcript in the format "SPEAKER_XX: text".

List the main topics or themes discussed in this portion. Topics should be \
concrete (e.g. agenda items, decisions, named projects or proposals), not \
generic (e.g. "Introduction" or "Discussion"). Typically 2-8 topics per portion; \
if none clearly apply, return an empty list: {{"main_topics": []}}. \
The transcript may be in Czech; keep topic labels in the same language. \
For each topic give a short label (a few words) and optionally a one-sentence \
description. Respond with a JSON object only, no other text, in this exact format:
{{"main_topics": [{{"id": "t1", "title": "short label", "description": "opt"}}, ...]}}

Transcript portion:
---
{chunk}
---
JSON:"""

# Phase 2: summarize discussion for one topic (topic + excerpt or full transcript).
PROMPT_TOPIC_SUMMARY = """You are analyzing a meeting/debate transcript. \
Below is the topic and the relevant part of the transcript.

Topic: {topic_title} (id: {topic_id})
Description: {topic_description}


Transcript (excerpt):
---
{excerpt}
---

Summarize the outcome or main points for this topic in 2-4 sentences. \
If this topic is not discussed in the excerpt, set summary to: \
[Topic not present in provided excerpt.] \
Respond with a JSON object only:
{{"topic_id": "{topic_id}", "summary": "..."}}

JSON:"""

# Phase 3: per-speaker contribution for one topic.
PROMPT_SPEAKER_CONTRIBUTIONS = """You are analyzing a meeting/debate transcript. \
For the topic below, summarize each speaker's position or contribution in one sentence.

Topic: {topic_title} (id: {topic_id})

Transcript excerpt:

---
{excerpt}
---

Respond with a JSON object only. Include one entry per speaker in the excerpt. \
Use the exact speaker IDs (e.g. SPEAKER_00) from the transcript. \
If this topic is not discussed in the excerpt, return: \
{{"speaker_contributions": [{{"topic_id": "{topic_id}", \
"speaker_id_in_transcript": "SPEAKER_UNKNOWN", "summary": "[Not in excerpt]"}}]}}. \
Otherwise use real speaker IDs and summaries.
{{"speaker_contributions": [{{"topic_id": "{topic_id}", \
"speaker_id_in_transcript": "SPEAKER_00", "summary": "..."}}, ...]}}
JSON:"""


def build_topics_chunk_prompt(chunk: str) -> str:
    """Build prompt for Phase 1 (topic extraction from one chunk)."""
    return PROMPT_TOPICS_CHUNK.format(chunk=chunk)


def build_topic_summary_prompt(
    topic_id: str,
    topic_title: str,
    topic_description: str,
    excerpt: str,
) -> str:
    """Build prompt for Phase 2 (summary for one topic)."""
    return PROMPT_TOPIC_SUMMARY.format(
        topic_id=topic_id,
        topic_title=topic_title,
        topic_description=topic_description or "(no description)",
        excerpt=excerpt,
    )


def build_speaker_contributions_prompt(
    topic_id: str,
    topic_title: str,
    excerpt: str,
) -> str:
    """Build prompt for Phase 3 (per-speaker contribution for one topic)."""
    return PROMPT_SPEAKER_CONTRIBUTIONS.format(
        topic_id=topic_id,
        topic_title=topic_title,
        excerpt=excerpt,
    )

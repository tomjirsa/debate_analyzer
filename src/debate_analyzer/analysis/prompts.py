"""Prompt templates for LLM transcript analysis phases."""

from __future__ import annotations

# Phase 1: extract topic labels from a chunk. (Braces in JSON escaped for .format.)
PROMPT_TOPICS_CHUNK = """List main topics in this transcript portion. Concrete only \
(agenda items, decisions, projects); 2-8; same language as transcript. \
Empty if none: {{"main_topics": []}}. JSON only:
{{"main_topics": [{{"id": "t1", "title": "short label", "description": "opt"}}, ...]}}

---
{chunk}
---
JSON:"""

# Phase 2: summarize discussion for one topic (topic + excerpt or full transcript).
PROMPT_TOPIC_SUMMARY = """Topic: {topic_title} (id: {topic_id})
Description: {topic_description}

Summarize only what the excerpt says about this topic in 2-4 sentences in Czech. \
If the excerpt does not discuss this topic, set summary to: \
[Téma v poskytnutém úryvku není obsaženo.]
JSON: {{"topic_id": "{topic_id}", "summary": "..."}}

Excerpt:
---
{excerpt}
---
JSON:"""

# Phase 3: per-speaker contribution for one topic.
PROMPT_SPEAKER_CONTRIBUTIONS = """Topic: {topic_title} (id: {topic_id})
One-sentence summary per speaker in Czech; use exact speaker IDs from transcript. \
If not in excerpt: {{"speaker_contributions": [{{"topic_id": "{topic_id}", \
"speaker_id_in_transcript": "SPEAKER_UNKNOWN", \
"summary": "[V úryvku není obsaženo]"}}]}}
{{"speaker_contributions": [{{"topic_id": "{topic_id}", \
"speaker_id_in_transcript": "SPEAKER_00", "summary": "..."}}, ...]}}

---
{excerpt}
---
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

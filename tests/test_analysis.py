"""Tests for LLM analysis module: chunking, runner with mock backend."""

from debate_analyzer.analysis.backend import MockLLMBackend
from debate_analyzer.analysis.chunking import (
    estimate_tokens,
    flatten_segments_to_text,
    flatten_transcription,
    flatten_transcription_with_indices,
    flatten_transcription_with_timestamps,
    get_topic_relevant_excerpt,
    get_topic_relevant_excerpt_with_range,
    segments_in_time_range,
    split_block_into_subchunks,
    split_into_chunks,
    split_into_chunks_with_time_ranges,
    topic_keywords,
    truncate_to_tokens,
)
from debate_analyzer.analysis.runner import run_analysis
from debate_analyzer.analysis.schema import LLMAnalysisResult


def test_flatten_transcription_empty():
    """Empty transcription yields empty string."""
    assert flatten_transcription([]) == ""


def test_flatten_transcription_single():
    """Single segment becomes one line."""
    t = [{"speaker": "SPEAKER_00", "text": "Hello world."}]
    assert flatten_transcription(t) == "SPEAKER_00: Hello world."


def test_flatten_transcription_multiple():
    """Multiple segments are joined by newline."""
    t = [
        {"speaker": "SPEAKER_00", "text": "First."},
        {"speaker": "SPEAKER_01", "text": "Second."},
    ]
    assert flatten_transcription(t) == "SPEAKER_00: First.\nSPEAKER_01: Second."


def test_flatten_transcription_with_indices_empty():
    """Empty transcription yields empty string and empty line_to_segment."""
    flat, line_to_segment = flatten_transcription_with_indices([])
    assert flat == ""
    assert line_to_segment == []


def test_flatten_transcription_with_indices_skips_empty_text():
    """Segments with empty text are omitted; line_to_segment maps to segment index."""
    t = [
        {"speaker": "SPEAKER_00", "text": "First."},
        {"speaker": "SPEAKER_01", "text": ""},
        {"speaker": "SPEAKER_02", "text": "Third."},
    ]
    flat, line_to_segment = flatten_transcription_with_indices(t)
    assert flat == "SPEAKER_00: First.\nSPEAKER_02: Third."
    assert line_to_segment == [0, 2]


def test_flatten_transcription_with_indices_all_non_empty():
    """When all segments have text, line index equals segment index."""
    t = [
        {"speaker": "SPEAKER_00", "text": "A"},
        {"speaker": "SPEAKER_01", "text": "B"},
    ]
    flat, line_to_segment = flatten_transcription_with_indices(t)
    assert line_to_segment == [0, 1]


def test_get_topic_relevant_excerpt_with_range_keyword_match():
    """Excerpt with range returns (excerpt, start_line, end_line) as topic span."""
    lines = [f"SPEAKER_00: Preamble {i}." for i in range(20)]
    lines.append("SPEAKER_01: UniqueWordXYZ here.")
    lines.extend([f"SPEAKER_00: Suffix {i}." for i in range(20)])
    flat = "\n".join(lines)
    excerpt, start, end = get_topic_relevant_excerpt_with_range(
        flat,
        topic_title="UniqueWordXYZ",
        topic_description="",
        max_tokens=500,
    )
    assert "UniqueWordXYZ" in excerpt
    assert start >= 0
    assert end >= start
    assert start == 20 and end == 20


def test_get_topic_relevant_excerpt_with_range_fallback():
    """Fallback returns range for staggered slice; end reflects truncated lines."""
    lines = [f"SPEAKER_00: Line {i}." for i in range(100)]
    flat = "\n".join(lines)
    excerpt, start, end = get_topic_relevant_excerpt_with_range(
        flat,
        topic_title="NonexistentTopic123",
        topic_description="",
        max_tokens=20,
        fallback_offset_index=2,
    )
    assert start == min(2 * 50, 99)
    assert end >= start
    assert len(excerpt.split("\n")) == end - start + 1


def test_estimate_tokens():
    """Token estimate is roughly length/4."""
    assert estimate_tokens("abcd") >= 1
    assert estimate_tokens("a" * 400) == 100


def test_topic_keywords():
    """topic_keywords returns sorted list from title/description (Czech included)."""
    kw = topic_keywords("Hlasování o rozpočtu", "")
    assert isinstance(kw, list)
    assert kw == sorted(kw)
    assert len(kw) == len(set(kw))
    assert "rozpočtu" in kw
    assert "hlasování" in kw


def test_split_into_chunks_short():
    """Short text returns one chunk."""
    text = "SPEAKER_00: Short."
    chunks = split_into_chunks(text, max_tokens=1000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_into_chunks_long():
    """Long text is split into multiple chunks with overlap."""
    lines = [f"SPEAKER_00: Line number {i}." for i in range(500)]
    text = "\n".join(lines)
    chunks = split_into_chunks(text, max_tokens=200, overlap_tokens=20)
    assert len(chunks) >= 2
    total_len = sum(len(c) for c in chunks)
    assert total_len >= len(text) * 0.9


def test_flatten_transcription_with_timestamps():
    """Timestamp-prefixed lines and line_times match; requires start/end."""
    t = [
        {"speaker": "SPEAKER_00", "text": "First.", "start": 0.0, "end": 5.0},
        {"speaker": "SPEAKER_01", "text": "Second.", "start": 5.0, "end": 10.0},
    ]
    flat, line_times = flatten_transcription_with_timestamps(t)
    assert "[0.00–5.00] SPEAKER_00: First." in flat
    assert "[5.00–10.00] SPEAKER_01: Second." in flat
    assert line_times == [(0.0, 5.0), (5.0, 10.0)]


def test_flatten_transcription_with_timestamps_normalizes_newlines():
    """Segment text with embedded newlines becomes one line so line_times match."""
    t = [
        {
            "speaker": "SPEAKER_00",
            "text": "Line one\nLine two",
            "start": 0.0,
            "end": 2.0,
        },
    ]
    flat, line_times = flatten_transcription_with_timestamps(t)
    assert flat.count("\n") == 0
    assert "Line one Line two" in flat
    assert len(line_times) == 1
    chunks = split_into_chunks_with_time_ranges(flat, line_times, max_tokens=500)
    assert len(chunks) == 1


def test_flatten_transcription_with_timestamps_raises_without_start_end():
    """Segments with non-empty text but no start/end raise ValueError."""
    import pytest

    t = [{"speaker": "SPEAKER_00", "text": "No times."}]
    with pytest.raises(ValueError, match="start.*end"):
        flatten_transcription_with_timestamps(t)


def test_segments_in_time_range():
    """Segments overlapping [start_sec, end_sec] are returned in order."""
    t = [
        {"speaker": "A", "text": "a", "start": 0.0, "end": 10.0},
        {"speaker": "B", "text": "b", "start": 10.0, "end": 20.0},
        {"speaker": "C", "text": "c", "start": 25.0, "end": 30.0},
    ]
    segs = segments_in_time_range(t, 5.0, 22.0)
    assert len(segs) == 2
    assert segs[0]["speaker"] == "A" and segs[1]["speaker"] == "B"


def test_flatten_segments_to_text():
    """Segments become SPEAKER: text lines without timestamp prefix."""
    segs = [
        {"speaker": "SPEAKER_00", "text": "Hello."},
        {"speaker": "SPEAKER_01", "text": "World."},
    ]
    text = flatten_segments_to_text(segs)
    assert text == "SPEAKER_00: Hello.\nSPEAKER_01: World."


def test_split_into_chunks_with_time_ranges():
    """Chunks get (text, start_sec, end_sec); single chunk when short."""
    lines = ["[0.00–1.00] S: A.", "[1.00–2.00] S: B."]
    flat = "\n".join(lines)
    line_times = [(0.0, 1.0), (1.0, 2.0)]
    chunks = split_into_chunks_with_time_ranges(flat, line_times, max_tokens=500)
    assert len(chunks) == 1
    assert chunks[0][0] == flat
    assert chunks[0][1] == 0.0 and chunks[0][2] == 2.0


def test_split_block_into_subchunks():
    """Long block text is split into subchunks by token limit."""
    lines = [f"SPEAKER_00: Line {i}." for i in range(100)]
    block = "\n".join(lines)
    subchunks = split_block_into_subchunks(block, max_tokens=50)
    assert len(subchunks) >= 2
    assert "".join(subchunks).replace("\n", "") == block.replace("\n", "")


def test_mock_backend_generate_batch():
    """Mock generate_batch returns one response per prompt in order."""
    backend = MockLLMBackend()
    prompts = ["prompt1", "prompt2", "prompt3"]
    out = backend.generate_batch(prompts, max_tokens=100)
    assert len(out) == 3
    assert all("speaker_contributions" in r for r in out)
    assert backend.call_count == 3


def test_run_analysis_empty_payload():
    """Empty transcription yields empty result."""
    backend = MockLLMBackend()
    result = run_analysis({"transcription": []}, backend.generate_batch)
    assert result["speaker_contributions"] == []


def test_run_analysis_returns_expected_shape():
    """run_analysis returns dict with speaker_contributions (empty)."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {"speaker": "SPEAKER_00", "text": "Topic one.", "start": 0.0, "end": 5.0},
            {"speaker": "SPEAKER_01", "text": "Topic two.", "start": 5.0, "end": 10.0},
        ]
    }
    result = run_analysis(payload, backend.generate_batch)
    assert "speaker_contributions" in result
    assert result["speaker_contributions"] == []
    assert backend.call_count == 0


def test_run_analysis_never_calls_generate_batch():
    """run_analysis does not call generate_batch (empty result path)."""
    backend = MockLLMBackend()
    run_analysis(
        {"transcription": [{"speaker": "S", "text": "x", "start": 0.0, "end": 1.0}]},
        backend.generate_batch,
    )
    assert backend.call_count == 0


def test_run_analysis_empty_transcription_no_contributions():
    """Empty transcription yields no speaker contributions."""
    backend = MockLLMBackend()
    result = run_analysis({"transcription": []}, backend.generate_batch)
    assert result["speaker_contributions"] == []


def test_run_analysis_no_timestamps_still_returns_empty():
    """Payload without timestamps still returns empty result (no LLM call)."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {"speaker": "SPEAKER_00", "text": "No timestamps."},
            {"speaker": "SPEAKER_01", "text": "Also none."},
        ]
    }
    result = run_analysis(payload, backend.generate_batch)
    assert result["speaker_contributions"] == []


def test_get_topic_relevant_excerpt_includes_matching_region():
    """Excerpt for a topic whose title appears only in the middle includes that part."""
    prefix = "\n".join([f"SPEAKER_00: Preamble line {i}." for i in range(30)])
    middle = "SPEAKER_01: UniqueKeywordXYZ here and only here."
    suffix = "\n".join([f"SPEAKER_00: Suffix line {i}." for i in range(30)])
    flat = prefix + "\n" + middle + "\n" + suffix
    excerpt = get_topic_relevant_excerpt(
        flat,
        topic_title="UniqueKeywordXYZ",
        topic_description="",
        max_tokens=500,
    )
    assert "UniqueKeywordXYZ" in excerpt
    assert estimate_tokens(excerpt) <= 500 + 50


def test_get_topic_relevant_excerpt_fallback_when_no_match():
    """When topic keywords do not appear, excerpt is start of transcript truncated."""
    flat = "\n".join([f"SPEAKER_00: Line {i}." for i in range(100)])
    excerpt = get_topic_relevant_excerpt(
        flat,
        topic_title="NonexistentTopic123",
        topic_description="",
        max_tokens=50,
    )
    assert "Line 0." in excerpt
    assert estimate_tokens(excerpt) <= 50 + 20


def test_get_topic_relevant_excerpt_prefix_match_czech():
    """Line with 'rozpočtu' matches topic keyword 'rozpočet' (prefix match)."""
    prefix = "\n".join([f"SPEAKER_00: Preamble {i}." for i in range(20)])
    middle = "SPEAKER_01: Hlasování o rozpočtu proběhlo v úterý."
    suffix = "\n".join([f"SPEAKER_00: Suffix {i}." for i in range(20)])
    flat = prefix + "\n" + middle + "\n" + suffix
    excerpt = get_topic_relevant_excerpt(
        flat,
        topic_title="Hlasování o rozpočtu",
        topic_description="",
        max_tokens=500,
    )
    assert "rozpočtu" in excerpt
    assert "Hlasování" in excerpt or "proběhlo" in excerpt


def test_get_topic_relevant_excerpt_staggered_fallback():
    """When no keyword match, fallback_offset_index yields different excerpt starts."""
    lines = [f"SPEAKER_00: Line {i}." for i in range(200)]
    flat = "\n".join(lines)
    excerpt0 = get_topic_relevant_excerpt(
        flat,
        topic_title="NonexistentXYZ",
        topic_description="",
        max_tokens=50,
        fallback_offset_index=0,
    )
    excerpt2 = get_topic_relevant_excerpt(
        flat,
        topic_title="NonexistentXYZ",
        topic_description="",
        max_tokens=50,
        fallback_offset_index=2,
    )
    assert "Line 0." in excerpt0
    assert "Line 100." in excerpt2
    assert excerpt0.strip() != excerpt2.strip()


def test_truncate_to_tokens_bounds_output():
    """truncate_to_tokens keeps output within token bound."""
    text = "\n".join([f"SPEAKER_00: Line {i}." for i in range(200)])
    out = truncate_to_tokens(text, max_tokens=100)
    assert estimate_tokens(out) <= 100 + 30


def test_llm_analysis_result_from_dict():
    """LLMAnalysisResult.from_dict parses raw dict with speaker_contributions only."""
    d = {
        "speaker_contributions": [
            {
                "id": "c1",
                "speaker_id_in_transcript": "SPEAKER_00",
                "summary": "In favor.",
                "keywords": ["klíčové", "slovo"],
            }
        ],
    }
    r = LLMAnalysisResult.from_dict(d)
    assert len(r.speaker_contributions) == 1
    assert r.speaker_contributions[0]["id"] == "c1"
    assert r.speaker_contributions[0]["speaker_id_in_transcript"] == "SPEAKER_00"
    assert r.speaker_contributions[0]["summary"] == "In favor."
    assert r.speaker_contributions[0]["keywords"] == ["klíčové", "slovo"]
    assert r.to_dict()["speaker_contributions"] == d["speaker_contributions"]


def test_get_backend_returns_mock_when_mock_llm_set():
    """_get_backend() returns mock generate_batch when MOCK_LLM=1."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"MOCK_LLM": "1"}, clear=False):
        from debate_analyzer.batch import llm_analysis_job

        generate_batch = llm_analysis_job._get_backend()
    out = generate_batch(["List the main topics"], max_tokens=100)
    assert len(out) == 1
    assert "speaker_contributions" in out[0]

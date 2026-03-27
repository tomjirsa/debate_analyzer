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
from debate_analyzer.analysis.schema import LLMAnalysisResult, SegmentSummary
from debate_analyzer.analysis.segment_summary_runner import (
    _parse_summary_json,
    run_segment_summaries,
)


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
    """Empty transcription yields empty segment_summaries."""
    backend = MockLLMBackend()
    result = run_analysis({"transcription": []}, backend.generate_batch)
    assert "segment_summaries" in result
    assert result["segment_summaries"] == []
    assert "speaker_contributions" in result
    assert result["speaker_contributions"] == []
    assert "transcript_summary" in result
    assert result["transcript_summary"]["summary"] == ""
    assert result["transcript_summary"]["keywords"] == []
    assert backend.call_count == 0


def test_run_analysis_returns_expected_shape():
    """run_analysis returns dict with segment_summaries (one per block)."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {
                "uid": "u1",
                "speaker": "SPEAKER_00",
                "text": "Topic one.",
                "start": 0.0,
                "end": 5.0,
            },
            {
                "uid": "u2",
                "speaker": "SPEAKER_01",
                "text": "Topic two.",
                "start": 5.0,
                "end": 10.0,
            },
        ]
    }
    result = run_analysis(payload, backend.generate_batch)
    assert "segment_summaries" in result
    assert len(result["segment_summaries"]) == 2
    assert result["segment_summaries"][0]["uid"] == "u1"
    assert result["segment_summaries"][0]["speaker"] == "SPEAKER_00"
    assert result["segment_summaries"][0]["start"] == 0.0
    assert result["segment_summaries"][0]["end"] == 5.0
    assert "Shrnutí" in result["segment_summaries"][0]["summary"]
    assert result["segment_summaries"][0]["keywords"]
    assert result["segment_summaries"][1]["uid"] == "u2"
    assert "speaker_contributions" in result
    assert len(result["speaker_contributions"]) == 2
    assert (
        result["speaker_contributions"][0]["speaker_id_in_transcript"] == "SPEAKER_00"
    )
    assert "transcript_summary" in result
    assert result["transcript_summary"]["summary"]
    assert result["transcript_summary"]["keywords"]
    # segment summaries (2 calls) + transcript merge (1 call; 2 speakers)
    assert backend.call_count == 3


def test_run_analysis_calls_generate_batch_per_block():
    """run_analysis calls generate_batch once per block with text."""
    backend = MockLLMBackend()
    run_analysis(
        {
            "transcription": [
                {
                    "uid": "u1",
                    "speaker": "S",
                    "text": "x",
                    "start": 0.0,
                    "end": 1.0,
                },
            ],
        },
        backend.generate_batch,
    )
    assert backend.call_count == 1


def test_run_analysis_empty_transcription_no_segment_summaries():
    """Empty transcription yields no segment summaries."""
    backend = MockLLMBackend()
    result = run_analysis({"transcription": []}, backend.generate_batch)
    assert result["segment_summaries"] == []
    assert result["speaker_contributions"] == []
    assert result["transcript_summary"]["summary"] == ""
    assert result["transcript_summary"]["keywords"] == []


def test_run_analysis_aggregates_speaker_contributions_and_transcript_summary():
    """Aggregate speaker segments into speaker_contributions and transcript_summary."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {
                "uid": "u1",
                "speaker": "SPEAKER_00",
                "text": "First segment.",
                "start": 0.0,
                "end": 5.0,
            },
            {
                "uid": "u2",
                "speaker": "SPEAKER_00",
                "text": "Second segment.",
                "start": 5.0,
                "end": 10.0,
            },
            {
                "uid": "u3",
                "speaker": "SPEAKER_01",
                "text": "Other speaker segment.",
                "start": 10.0,
                "end": 15.0,
            },
        ]
    }
    result = run_analysis(payload, backend.generate_batch)
    assert len(result["speaker_contributions"]) == 2

    speaker_ids = [
        c["speaker_id_in_transcript"] for c in result["speaker_contributions"]
    ]
    assert speaker_ids == ["SPEAKER_00", "SPEAKER_01"]

    # For SPEAKER_00 we have 2 partial summaries -> merge prompt is used.
    speaker_00 = result["speaker_contributions"][0]
    assert speaker_00["summary"] == "Slučené shrnutí."
    assert speaker_00["keywords"] == ["sloučený"]

    assert result["transcript_summary"]["summary"] == "Slučené shrnutí."
    assert result["transcript_summary"]["keywords"] == ["sloučený"]

    # segment summaries (3) + speaker merge for SPEAKER_00 (1) + transcript merge (1)
    assert backend.call_count == 5


def test_run_analysis_no_timestamps_uses_defaults_and_returns_records():
    """Payload without uid/start/end still processed; defaults used."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {"speaker": "SPEAKER_00", "text": "No timestamps."},
            {"speaker": "SPEAKER_01", "text": "Also none."},
        ]
    }
    result = run_analysis(payload, backend.generate_batch)
    assert "segment_summaries" in result
    assert len(result["segment_summaries"]) == 2
    assert result["segment_summaries"][0]["speaker"] == "SPEAKER_00"
    assert result["segment_summaries"][0]["start"] == 0.0
    assert result["segment_summaries"][0]["end"] == 0.0


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
    """LLMAnalysisResult.from_dict parses speaker_contributions or segment_summaries."""
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

    d2 = {
        "segment_summaries": [
            {
                "uid": "u1",
                "speaker": "SPEAKER_00",
                "start": 0.0,
                "end": 10.5,
                "summary": "Shrnutí.",
                "keywords": ["a", "b"],
            }
        ],
    }
    r2 = LLMAnalysisResult.from_dict(d2)
    assert len(r2.segment_summaries) == 1
    assert r2.segment_summaries[0]["uid"] == "u1"
    assert r2.segment_summaries[0]["start"] == 0.0
    assert r2.segment_summaries[0]["end"] == 10.5
    assert r2.to_dict()["segment_summaries"] == d2["segment_summaries"]

    d3 = {
        "transcript_summary": {
            "summary": "Celkové shrnutí.",
            "keywords": ["témata", "hlasování"],
        }
    }
    r3 = LLMAnalysisResult.from_dict(d3)
    assert r3.to_dict()["transcript_summary"] == d3["transcript_summary"]


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


def test_parse_summary_json_valid():
    """_parse_summary_json extracts summary and keywords from valid JSON."""
    raw = '{"summary": "Shrnutí.", "keywords": ["a", "b"]}'
    summary, keywords = _parse_summary_json(raw)
    assert summary == "Shrnutí."
    assert keywords == ["a", "b"]


def test_parse_summary_json_with_surrounding_text():
    """_parse_summary_json finds JSON object inside surrounding text."""
    raw = 'Here is the result:\n{"summary": "Ok.", "keywords": ["x"]}\nDone.'
    summary, keywords = _parse_summary_json(raw)
    assert summary == "Ok."
    assert keywords == ["x"]


def test_parse_summary_json_invalid_returns_empty():
    """_parse_summary_json returns empty on invalid or missing JSON."""
    assert _parse_summary_json("") == ("", [])
    assert _parse_summary_json("not json") == ("", [])
    assert _parse_summary_json("{}") == ("", [])


def test_parse_summary_json_rejects_shrnuti_key():
    """Czech key shrnutí is not accepted in place of summary."""
    raw = '{"shrnutí": "text", "keywords": ["a"]}'
    assert _parse_summary_json(raw) == ("", [])


def test_parse_summary_json_strips_markdown_fence():
    """JSON inside ``` fences is parsed."""
    raw = '```json\n{"summary": "Ok.", "keywords": ["x"]}\n```'
    summary, keywords = _parse_summary_json(raw)
    assert summary == "Ok."
    assert keywords == ["x"]


def test_run_segment_summaries_retries_once_after_bad_first_response():
    """Second generate_batch call supplies valid JSON after first parse failure."""
    calls: list[int] = []

    def gen_batch(prompts, max_tokens=2048, **kwargs):
        calls.append(len(prompts))
        if len(calls) == 1:
            return ["not valid json"]
        return ['{"summary": "Shrnutí po opakování.", "keywords": ["a"]}']

    payload = {
        "transcription": [
            {
                "uid": "u1",
                "speaker": "S",
                "text": "word " * 20,
                "start": 0,
                "end": 1,
            },
        ],
    }
    result = run_segment_summaries(payload, gen_batch, max_context_tokens=8000)
    assert len(calls) == 2
    assert len(result) == 1
    assert result[0]["summary"] == "Shrnutí po opakování."
    assert result[0]["keywords"] == ["a"]


def test_segment_summary_from_dict_to_dict():
    """SegmentSummary.from_dict and to_dict round-trip."""
    d = {
        "uid": "u1",
        "speaker": "SPEAKER_00",
        "start": 0.0,
        "end": 10.5,
        "summary": "S.",
        "keywords": ["k1"],
    }
    seg = SegmentSummary.from_dict(d)
    assert seg.uid == "u1"
    assert seg.speaker == "SPEAKER_00"
    assert seg.start == 0.0
    assert seg.end == 10.5
    assert seg.summary == "S."
    assert seg.keywords == ["k1"]
    assert seg.to_dict() == d


def test_run_segment_summaries_skips_empty_text():
    """run_segment_summaries skips blocks with empty text."""

    def gen_batch(prompts, max_tokens=2048, **kwargs):
        return ['{"summary": "x", "keywords": []}'] * len(prompts)

    payload = {
        "transcription": [
            {"uid": "u1", "speaker": "S", "text": "", "start": 0, "end": 1},
            {"uid": "u2", "speaker": "S", "text": "  \n  ", "start": 1, "end": 2},
            {"uid": "u3", "speaker": "S", "text": "one word", "start": 2, "end": 3},
        ],
    }
    result = run_segment_summaries(payload, gen_batch, max_context_tokens=8000)
    assert len(result) == 1
    assert result[0]["uid"] == "u3"
    assert result[0]["start"] == 2.0
    assert result[0]["end"] == 3.0


def test_run_segment_summaries_skips_short_segments_when_min_words_set():
    """run_segment_summaries skips segments with word count below min_words."""

    def gen_batch(prompts, max_tokens=2048, **kwargs):
        return ['{"summary": "ok", "keywords": ["k"]}'] * len(prompts)

    payload = {
        "transcription": [
            {"uid": "u1", "speaker": "S", "text": "", "start": 0, "end": 1},
            {"uid": "u2", "speaker": "S", "text": "one", "start": 1, "end": 2},
            {"uid": "u3", "speaker": "S", "text": "a b", "start": 2, "end": 3},
            {
                "uid": "u4",
                "speaker": "S",
                "text": "one two three four five",
                "start": 3,
                "end": 4,
            },
        ],
    }
    result = run_segment_summaries(
        payload, gen_batch, max_context_tokens=8000, min_words=3
    )
    assert len(result) == 1
    assert result[0]["uid"] == "u4"
    assert result[0]["summary"] == "ok"


def test_run_segment_summaries_min_words_zero_summarizes_all_non_empty():
    """With min_words=0, all non-empty segments are summarized (backward compat)."""

    def gen_batch(prompts, max_tokens=2048, **kwargs):
        return ['{"summary": "x", "keywords": []}'] * len(prompts)

    payload = {
        "transcription": [
            {"uid": "u1", "speaker": "S", "text": "one", "start": 0, "end": 1},
            {"uid": "u2", "speaker": "S", "text": "two words", "start": 1, "end": 2},
        ],
    }
    result = run_segment_summaries(
        payload, gen_batch, max_context_tokens=8000, min_words=0
    )
    assert len(result) == 2
    assert result[0]["uid"] == "u1"
    assert result[1]["uid"] == "u2"


def test_run_segment_summaries_preserves_uid_and_metadata():
    """run_segment_summaries preserves uid, speaker, start, end from block."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {
                "uid": "my-uid-123",
                "speaker": "SPEAKER_07",
                "text": "Short segment.",
                "start": 100.5,
                "end": 105.25,
            },
        ],
    }
    result = run_segment_summaries(payload, backend.generate_batch)
    assert len(result) == 1
    assert result[0]["uid"] == "my-uid-123"
    assert result[0]["speaker"] == "SPEAKER_07"
    assert result[0]["start"] == 100.5
    assert result[0]["end"] == 105.25
    assert "summary" in result[0]
    assert "keywords" in result[0]

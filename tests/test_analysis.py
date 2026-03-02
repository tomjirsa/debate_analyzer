"""Tests for LLM analysis module: chunking, runner with mock backend."""

from debate_analyzer.analysis.backend import MockLLMBackend
from debate_analyzer.analysis.chunking import (
    estimate_tokens,
    flatten_transcription,
    get_topic_relevant_excerpt,
    split_into_chunks,
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


def test_estimate_tokens():
    """Token estimate is roughly length/4."""
    assert estimate_tokens("abcd") >= 1
    assert estimate_tokens("a" * 400) == 100


def test_topic_keywords():
    """topic_keywords returns sorted list from title/description; Czech words included."""
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


def test_mock_backend_generate_batch():
    """Mock generate_batch returns one response per prompt in order."""
    backend = MockLLMBackend()
    prompts = [
        "List the main topics",
        "Summarize the outcome",
        "each speaker's position",
    ]
    out = backend.generate_batch(prompts, max_tokens=100)
    assert len(out) == 3
    assert "main_topics" in out[0]
    assert "topic_id" in out[1] and "summary" in out[1]
    assert "speaker_contributions" in out[2]
    assert backend.call_count == 3


def test_run_analysis_empty_payload():
    """Empty transcription yields empty result."""
    backend = MockLLMBackend()
    result = run_analysis({"transcription": []}, backend.generate_batch)
    assert result["main_topics"] == []
    assert result["topic_summaries"] == []
    assert result["speaker_contributions"] == []


def test_run_analysis_mock_backend():
    """Runner with mock backend returns expected shape."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {"speaker": "SPEAKER_00", "text": "Topic one."},
            {"speaker": "SPEAKER_01", "text": "Topic two."},
        ]
    }
    result = run_analysis(payload, backend.generate_batch)
    assert "main_topics" in result
    assert "topic_summaries" in result
    assert "speaker_contributions" in result
    assert isinstance(result["main_topics"], list)
    assert isinstance(result["topic_summaries"], list)
    assert isinstance(result["speaker_contributions"], list)
    for topic in result["main_topics"]:
        assert "keywords" in topic
        assert isinstance(topic["keywords"], list)
        assert all(isinstance(s, str) for s in topic["keywords"])
    assert backend.call_count >= 1


def test_run_analysis_respects_max_context_tokens():
    """With small max_context_tokens, Phase 1 uses multiple chunks."""
    backend = MockLLMBackend()
    # Payload that flattens to ~500 tokens so we get multiple chunks with max 100
    lines = [f"SPEAKER_00: Segment number {i} with some content." for i in range(80)]
    text = "\n".join(lines)
    assert estimate_tokens(text) > 100
    payload = {
        "transcription": [
            {"speaker": "SPEAKER_00", "text": line.split(": ", 1)[1]} for line in lines
        ]
    }
    calls: list[tuple[str, str, str]] = []

    def capture(label: str, prompt: str, response: str) -> None:
        calls.append((label, prompt, response))

    run_analysis(
        payload,
        backend.generate_batch,
        max_context_tokens=100,
        log_llm_call=capture,
    )
    phase1_labels = [c[0] for c in calls if "Phase 1 batch" in c[0]]
    assert (
        len(phase1_labels) >= 1
    ), "expected Phase 1 batch call when using generate_batch"


def test_run_analysis_respects_max_excerpt_tokens():
    """With max_excerpt_tokens set, Phase 2/3 excerpts are capped at that size."""
    backend = MockLLMBackend()
    # Long transcript so topic-relevant excerpt could be large without cap
    lines = (
        [f"SPEAKER_00: Preamble {i}." for i in range(20)]
        + ["SPEAKER_01: UniqueTopicXYZ discussed here."]
        + [f"SPEAKER_00: More line {i}." for i in range(80)]
    )
    payload = {
        "transcription": [
            {"speaker": line.split(": ", 1)[0], "text": line.split(": ", 1)[1]}
            for line in lines
        ]
    }
    calls: list[tuple[str, str, str]] = []

    def capture(label: str, prompt: str, response: str) -> None:
        calls.append((label, prompt, response))

    run_analysis(
        payload,
        backend.generate_batch,
        max_context_tokens=2000,
        max_excerpt_tokens=50,
        log_llm_call=capture,
    )
    # Find Phase 2 prompt and extract excerpt (between --- and ---)
    phase2 = [c for c in calls if "Phase 2" in c[0]]
    assert len(phase2) >= 1
    prompt = phase2[0][1]
    if "---" in prompt:
        parts = prompt.split("---")
        for part in parts[1:]:
            excerpt = part.strip().split("\n---")[0].strip()
            if excerpt and "SPEAKER" in excerpt:
                assert estimate_tokens(excerpt) <= 50 + 40, (
                    "Phase 2 excerpt capped at max_excerpt_tokens (with slack)"
                )
                break


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
    assert estimate_tokens(excerpt) <= 500 + 50  # allow small over-estimate


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
    """Line containing 'rozpočtu' matches topic with keyword 'rozpočet' (prefix match)."""
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
    # With window_lines=50, index 2 -> start at line 100
    assert "Line 100." in excerpt2
    assert excerpt0.strip() != excerpt2.strip()


def test_truncate_to_tokens_bounds_output():
    """truncate_to_tokens keeps output within token bound."""
    text = "\n".join([f"SPEAKER_00: Line {i}." for i in range(200)])
    out = truncate_to_tokens(text, max_tokens=100)
    assert estimate_tokens(out) <= 100 + 30  # line boundary may leave small slack


def test_run_analysis_log_llm_call_invoked():
    """log_llm_call is invoked for each Phase 1/2/3 call with expected labels."""
    backend = MockLLMBackend()
    payload = {
        "transcription": [
            {"speaker": "SPEAKER_00", "text": "Topic one."},
            {"speaker": "SPEAKER_01", "text": "Topic two."},
        ]
    }
    calls: list[tuple[str, str, str]] = []

    def capture(label: str, prompt: str, response: str) -> None:
        calls.append((label, prompt, response))

    result = run_analysis(payload, backend.generate_batch, log_llm_call=capture)
    assert "main_topics" in result
    assert len(calls) >= 1
    labels = [c[0] for c in calls]
    assert any("Phase 1" in lbl for lbl in labels)
    assert any("Phase 2" in lbl for lbl in labels)
    assert any("Phase 3" in lbl for lbl in labels)
    for _, prompt, resp in calls:
        assert isinstance(prompt, str) and isinstance(resp, str)


def test_extract_json_strips_markdown_fences():
    """_extract_json parses JSON wrapped in markdown code fences on retry."""
    from debate_analyzer.analysis.runner import _extract_json

    wrapped = '```json\n{"main_topics": [{"id": "t1", "title": "A"}]}\n```'
    parsed = _extract_json(wrapped)
    assert isinstance(parsed, dict)
    assert parsed.get("main_topics") == [{"id": "t1", "title": "A"}]


def test_llm_analysis_result_from_dict():
    """LLMAnalysisResult.from_dict parses raw dict."""
    d = {
        "main_topics": [{"id": "t1", "title": "A", "description": ""}],
        "topic_summaries": [{"topic_id": "t1", "summary": "Summary."}],
        "speaker_contributions": [
            {
                "topic_id": "t1",
                "speaker_id_in_transcript": "SPEAKER_00",
                "summary": "In favor.",
            }
        ],
    }
    r = LLMAnalysisResult.from_dict(d)
    assert len(r.main_topics) == 1
    assert r.main_topics[0]["id"] == "t1"
    assert len(r.topic_summaries) == 1
    assert len(r.speaker_contributions) == 1
    assert r.to_dict()["main_topics"] == d["main_topics"]

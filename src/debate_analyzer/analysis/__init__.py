"""LLM transcript analysis: segment summaries and (legacy) speaker contributions."""

from debate_analyzer.analysis.runner import run_analysis
from debate_analyzer.analysis.schema import (
    LLMAnalysisResult,
    SegmentSummary,
    SpeakerContribution,
)

__all__ = [
    "LLMAnalysisResult",
    "run_analysis",
    "SegmentSummary",
    "SpeakerContribution",
]

"""LLM-based transcript analysis: speaker contributions only."""

from debate_analyzer.analysis.runner import run_analysis
from debate_analyzer.analysis.schema import LLMAnalysisResult, SpeakerContribution

__all__ = [
    "LLMAnalysisResult",
    "run_analysis",
    "SpeakerContribution",
]

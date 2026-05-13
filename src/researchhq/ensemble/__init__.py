"""Parallel multi-model ensemble intelligence pipeline for ResearchHQ.

Runs multiple AI providers simultaneously, extracts and compares claims,
builds consensus, scores confidence, and synthesizes a higher-quality report.
"""

from researchhq.ensemble.claim_extractor import Claim, extract_claims, extract_all_claims
from researchhq.ensemble.consensus import ClaimGroup, ConsensusResult, analyze_consensus
from researchhq.ensemble.confidence import ConfidenceReport, score_confidence
from researchhq.ensemble.disagreement import Disagreement, DisagreementReport, analyze_disagreements
from researchhq.ensemble.merger import EnsembleMeta, merge_synthesis
from researchhq.ensemble.orchestrator import EnsembleRun, ProviderResult, run_parallel
from researchhq.ensemble.verifier import EnsembleVerifierNote, verify_synthesis

__all__ = [
    "Claim", "extract_claims", "extract_all_claims",
    "ClaimGroup", "ConsensusResult", "analyze_consensus",
    "ConfidenceReport", "score_confidence",
    "Disagreement", "DisagreementReport", "analyze_disagreements",
    "EnsembleMeta", "merge_synthesis",
    "EnsembleRun", "ProviderResult", "run_parallel",
    "EnsembleVerifierNote", "verify_synthesis",
]

"""Pydantic models and schemas defining domain contracts across module boundaries."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

# Result Statuses
StatusType = Literal["eligible", "rejected", "failed"]

# GitHub Statuses
GitHubStatus = Literal[
    "ok",
    "no_profile",
    "not_found",
    "rate_limited",
    "error",
    "disabled",
    "skipped_rejected",
]

# Capability Keys (LLM Extraction)
CapabilityKey = Literal[
    "llm_call",
    "retrieval_rag",
    "tool_calling",
    "multi_agent",
    "state_orchestration",
    "evaluation_guardrails",
    "business_logic_data",
]

# Signal Keys (Backend, Cloud, Full Stack, Engineering)
SignalKey = Literal[
    "python",
    "fastapi",
    "flask_django",
    "async_programming",
    "postgresql",
    "other_sql",
    "redis",
    "gcp",
    "other_cloud",
    "docker",
    "deployment",
    "ci_cd",
    "react_nextjs",
    "testing",
    "architecture_design",
    "caching_queues",
    "observability",
    "concurrency_failure_handling",
]

Context = Literal["skills_only", "applied"]


class CandidateFile(BaseModel):
    """Metadata for an ingested file."""
    path: Path
    filename: str
    size_bytes: int
    sha256: str
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None


class ParsedDocument(BaseModel):
    """Result of parsing a document file."""
    text: str
    hyperlinks: List[str] = Field(default_factory=list)
    page_count: int = 1
    normalized_text_hash: str = ""


class EligibilityResult(BaseModel):
    """Result of pure deterministic eligibility check."""
    eligible: bool
    rejection_reasons: List[str] = Field(default_factory=list)
    matched_skills: List[str] = Field(default_factory=list)
    needs_review: bool = False
    python_ok: bool = False
    ai_ok: bool = False
    warnings: List[str] = Field(default_factory=list)


class ProjectEvidence(BaseModel):
    name: str
    summary: str = Field(..., max_length=300)
    technologies: List[str] = Field(default_factory=list)
    is_ai_project: bool = False
    capabilities: List[CapabilityKey] = Field(default_factory=list)
    is_thin_wrapper: bool = False
    is_tutorial_style: bool = False
    ownership_evidence: bool = True
    quotes: List[str] = Field(default_factory=list)


class Signal(BaseModel):
    key: SignalKey
    context: Context
    quote: str


class ResumeExtraction(BaseModel):
    schema_version: str = SCHEMA_VERSION
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    github_url: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    projects: List[ProjectEvidence] = Field(default_factory=list)
    signals: List[Signal] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    ai_project_depth: int
    python_backend: int
    cloud_fullstack: int
    github: int
    engineering_depth: int


class Adjustment(BaseModel):
    reason: str
    points: int


class EvidenceItem(BaseModel):
    category: str
    capability: Optional[str] = None
    signal: Optional[str] = None
    quote: str


class GitHubResult(BaseModel):
    status: GitHubStatus
    username: Optional[str] = None
    activity_points: int = 0
    repo_points: int = 0
    summary: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class CandidateResult(BaseModel):
    """Final output schema for each candidate."""
    rank: Optional[int] = None
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    source_file: str
    status: StatusType
    eligible: Optional[bool] = None
    total_score: Optional[int] = None
    score_breakdown: Optional[ScoreBreakdown] = None
    adjustments: List[Adjustment] = Field(default_factory=list)
    matched_skills: List[str] = Field(default_factory=list)
    project_summary: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    github_summary: Optional[str] = None
    github: Optional[GitHubResult] = None
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    scoring_mode: Optional[Literal["llm", "heuristic"]] = None
    warnings: List[str] = Field(default_factory=list)
    failure_reason: Optional[str] = None
    rejection_reasons: List[str] = Field(default_factory=list)


class BatchSummary(BaseModel):
    """Summary of batch run with invariants."""
    schema_version: str = SCHEMA_VERSION
    total_files: int
    duplicates_skipped: int
    unique_processed: int
    parsed: int
    failed: int
    eligible: int
    rejected: int
    timings: Dict[str, float] = Field(default_factory=dict)

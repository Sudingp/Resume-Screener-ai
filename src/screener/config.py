"""Configuration loading, validation, and typed settings."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator


class ConfigError(Exception):
    """Raised when configuration values fail validation or required files are missing."""
    pass


class CategoryWeights(BaseModel):
    ai_project_depth: int = 40
    python_backend: int = 30
    cloud_fullstack: int = 15
    github: int = 10
    engineering_depth: int = 5

    @model_validator(mode="after")
    def validate_total_weight(self) -> "CategoryWeights":
        total = (
            self.ai_project_depth
            + self.python_backend
            + self.cloud_fullstack
            + self.github
            + self.engineering_depth
        )
        if total != 100:
            raise ValueError(f"Category weights must sum to 100, got {total}")
        return self


class AIDepthConfig(BaseModel):
    capabilities: Dict[str, int]
    skills_only_max: int = 4
    category_cap: int = 40


class PythonBackendConfig(BaseModel):
    credits: Dict[str, List[int]]  # [applied, skills_only]
    category_cap: int = 30


class CloudFullstackConfig(BaseModel):
    credits: Dict[str, List[int]]
    category_cap: int = 15


class GitHubScoringConfig(BaseModel):
    activity_max: int = 5
    repos_max: int = 5
    category_cap: int = 10
    min_repo_size_kb: int = 50
    recency_days: Dict[str, List[int]]
    active_weeks_90d: Dict[str, List[int]]
    maintained_repos_365d: Dict[str, List[int]]
    relevant_repos: Dict[str, List[int]]


class EngineeringDepthConfig(BaseModel):
    points_per_applied_signal: int = 1
    signals: List[str]
    category_cap: int = 5


class PenaltiesConfig(BaseModel):
    thin_wrapper_penalty: int = -10
    tutorial_style_penalty: int = -5
    max_total_penalty: int = 15


class ThresholdsConfig(BaseModel):
    no_meaningful_ai_threshold: int = 12
    no_meaningful_ai_cap: int = 55
    heuristic_ai_depth_cap: int = 24

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ThresholdsConfig":
        if self.no_meaningful_ai_threshold <= 0:
            raise ValueError("no_meaningful_ai_threshold must be positive")
        if not (0 <= self.no_meaningful_ai_cap <= 100):
            raise ValueError("no_meaningful_ai_cap must be between 0 and 100")
        return self


class ScoringConfig(BaseModel):
    category_weights: CategoryWeights
    ai_project_depth: AIDepthConfig
    python_backend: PythonBackendConfig
    cloud_fullstack: CloudFullstackConfig
    github: GitHubScoringConfig
    engineering_depth: EngineeringDepthConfig
    penalties: PenaltiesConfig
    thresholds: ThresholdsConfig


class EligibilityLexicons(BaseModel):
    medium_requires_verb: bool = True
    classical_ml_counts: bool = False
    python_patterns: List[str]
    strong_ai_terms: List[str]
    medium_ai_terms: List[str]
    weak_ai_terms: List[str]
    implementation_verbs: List[str]


class LexiconsConfig(BaseModel):
    eligibility: EligibilityLexicons
    skills_catalog: List[str]
    signal_patterns: Dict[str, List[str]]


class RuntimeConfig(BaseModel):
    llm_provider: str = "gemini"
    llm_model: str = "gemini-1.5-flash"
    llm_api_key: Optional[str] = None
    llm_enabled: bool = True
    github_token: Optional[str] = None
    github_enabled: bool = True
    llm_concurrency: int = 4
    github_concurrency: int = 4
    llm_timeout_seconds: float = 60.0
    github_timeout_seconds: float = 10.0
    max_file_size_mb: int = 10
    max_pdf_pages: int = 10
    max_text_chars: int = 20000


class AppConfig(BaseModel):
    scoring: ScoringConfig
    lexicons: LexiconsConfig
    runtime: RuntimeConfig


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data is not None else {}
    except Exception as e:
        raise ConfigError(f"Error parsing YAML from {path}: {e}") from e


def load_config(
    config_dir: Optional[Path] = None,
    scoring_file: Optional[Path] = None,
    lexicons_file: Optional[Path] = None,
    env_file: Optional[Path] = None,
    no_llm: bool = False,
    no_github: bool = False,
    concurrency: Optional[int] = None,
) -> AppConfig:
    """Load configuration from YAML files and environment variables."""
    # Find project root or config_dir
    base_dir = Path(__file__).resolve().parent.parent.parent
    c_dir = config_dir or (base_dir / "config")

    s_file = scoring_file or (c_dir / "scoring.yaml")
    l_file = lexicons_file or (c_dir / "lexicons.yaml")

    # Load environment
    if env_file and env_file.is_file():
        load_dotenv(env_file)
    else:
        load_dotenv(base_dir / ".env")

    scoring_data = load_yaml(s_file)
    lexicons_data = load_yaml(l_file)

    try:
        scoring = ScoringConfig.model_validate(scoring_data)
    except Exception as e:
        raise ConfigError(f"Invalid scoring configuration: {e}") from e

    try:
        lexicons = LexiconsConfig.model_validate(lexicons_data)
    except Exception as e:
        raise ConfigError(f"Invalid lexicons configuration: {e}") from e

    llm_enabled = not no_llm
    github_enabled = not no_github

    llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    llm_model = os.getenv("LLM_MODEL", "gemini-1.5-flash")
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")

    if llm_enabled and not llm_api_key:
        # Per blueprint: missing env key only errors when the LLM is enabled AND live mode is requested
        # Can still fall back or require explicit --no-llm
        pass

    github_token = os.getenv("GITHUB_TOKEN")

    default_concurrency = int(os.getenv("LLM_CONCURRENCY", "4"))
    actual_concurrency = concurrency if concurrency is not None else default_concurrency

    runtime = RuntimeConfig(
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
        llm_enabled=llm_enabled,
        github_token=github_token,
        github_enabled=github_enabled,
        llm_concurrency=actual_concurrency,
        github_concurrency=int(os.getenv("GITHUB_CONCURRENCY", str(actual_concurrency))),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60.0")),
        github_timeout_seconds=float(os.getenv("GITHUB_TIMEOUT_SECONDS", "10.0")),
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "10")),
        max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", "10")),
        max_text_chars=int(os.getenv("MAX_TEXT_CHARS", "20000")),
    )

    return AppConfig(scoring=scoring, lexicons=lexicons, runtime=runtime)

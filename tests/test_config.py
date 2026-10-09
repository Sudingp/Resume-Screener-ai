"""Tests for configuration loading and validation."""

import pytest
from pathlib import Path
from screener.config import load_config, ConfigError, CategoryWeights, ThresholdsConfig


def test_valid_config_loads():
    cfg = load_config()
    assert cfg.scoring.category_weights.ai_project_depth == 40
    assert cfg.scoring.category_weights.python_backend == 30
    assert cfg.scoring.category_weights.cloud_fullstack == 15
    assert cfg.scoring.category_weights.github == 10
    assert cfg.scoring.category_weights.engineering_depth == 5
    # Total sum is 100
    total = (
        cfg.scoring.category_weights.ai_project_depth
        + cfg.scoring.category_weights.python_backend
        + cfg.scoring.category_weights.cloud_fullstack
        + cfg.scoring.category_weights.github
        + cfg.scoring.category_weights.engineering_depth
    )
    assert total == 100


def test_category_weights_must_sum_to_100():
    with pytest.raises(ValueError, match="Category weights must sum to 100"):
        CategoryWeights(
            ai_project_depth=40,
            python_backend=30,
            cloud_fullstack=15,
            github=10,
            engineering_depth=10,  # Sum is 105
        )


def test_invalid_thresholds():
    with pytest.raises(ValueError):
        ThresholdsConfig(
            no_meaningful_ai_threshold=0,
            no_meaningful_ai_cap=55,
            heuristic_ai_depth_cap=24,
        )

    with pytest.raises(ValueError):
        ThresholdsConfig(
            no_meaningful_ai_threshold=12,
            no_meaningful_ai_cap=120,
            heuristic_ai_depth_cap=24,
        )


def test_missing_config_file_raises():
    with pytest.raises(ConfigError):
        load_config(scoring_file=Path("non_existent_file.yaml"))

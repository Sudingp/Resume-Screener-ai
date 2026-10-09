"""Integration tests verifying full pipeline execution, invariant verification, and error isolation."""

import json
from pathlib import Path
import pytest
from screener.config import load_config
from screener.llm.fake import FakeLLM
from screener.pipeline import run_screening_pipeline
from screener.report import write_reports_atomically
from screener.models import CandidateResult, BatchSummary

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "resumes"


@pytest.mark.asyncio
async def test_full_pipeline_synthetic_fixtures(tmp_path):
    cfg = load_config(no_github=True)
    fake_llm = FakeLLM()

    results, summary = await run_screening_pipeline(
        input_dir=FIXTURES_DIR,
        config=cfg,
        llm_client=fake_llm,
        cache_dir=tmp_path / "cache",
    )

    # 1. Verify Summary Invariants
    # files_found = duplicates_skipped + unique_processed
    assert summary.total_files == summary.duplicates_skipped + summary.unique_processed
    # unique_processed = parsed + failed
    assert summary.unique_processed == summary.parsed + summary.failed
    # parsed = eligible + rejected
    assert summary.parsed == summary.eligible + summary.rejected

    # 2. Check result statuses are represented
    statuses = {r.status for r in results}
    assert "eligible" in statuses
    assert "rejected" in statuses
    assert "failed" in statuses

    # 3. Check ordering: all eligible first (with ranks 1..N), then rejected, then failed
    seen_rejected = False
    seen_failed = False
    prev_rank = 0

    for r in results:
        if r.status == "eligible":
            assert not seen_rejected, "Eligible candidate appeared after rejected candidate"
            assert not seen_failed, "Eligible candidate appeared after failed file"
            assert r.rank is not None
            assert r.rank == prev_rank + 1
            prev_rank = r.rank
            assert r.total_score is not None
            assert r.score_breakdown is not None
        elif r.status == "rejected":
            seen_rejected = True
            assert not seen_failed, "Rejected candidate appeared after failed file"
            assert r.rank is None
            assert r.eligible is False
            assert len(r.rejection_reasons) > 0
        elif r.status == "failed":
            seen_failed = True
            assert r.rank is None
            assert r.failure_reason is not None

    # 4. Atomic report writing verification
    out_json = tmp_path / "results.json"
    sum_json = tmp_path / "summary.json"
    write_reports_atomically(results, summary, out_json, sum_json, write_csv=True)

    assert out_json.is_file()
    assert sum_json.is_file()
    assert (tmp_path / "results.csv").is_file()

    with open(out_json, "r", encoding="utf-8") as f:
        loaded = json.load(f)
        assert isinstance(loaded, list)
        assert len(loaded) == len(results)


@pytest.mark.asyncio
async def test_pipeline_with_failing_llm_falls_back_to_heuristic(tmp_path):
    cfg = load_config(no_github=True)
    failing_llm = FakeLLM(should_fail=True)

    results, summary = await run_screening_pipeline(
        input_dir=FIXTURES_DIR,
        config=cfg,
        llm_client=failing_llm,
        cache_dir=tmp_path / "cache",
    )

    eligible = [r for r in results if r.status == "eligible"]
    assert len(eligible) > 0
    # Eligible candidates should have fallen back to heuristic scoring with warning
    for r in eligible:
        assert r.scoring_mode == "heuristic"
        assert any("heuristic" in w.lower() for w in r.warnings)

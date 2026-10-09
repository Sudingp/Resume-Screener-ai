"""Benchmark concurrency speedup on the real resume dataset using fixed-delay FakeLLM."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from screener.config import load_config
from screener.llm.fake import FakeLLM
from screener.pipeline import run_screening_pipeline


async def run_benchmark():
    resumes_dir = Path("resumes")
    if not resumes_dir.is_dir():
        print("Resumes directory not found.")
        return

    print("Benchmarking Concurrency on 50 Resumes with 0.1s simulated LLM latency...")

    # Run 1: Concurrency 1
    cfg_c1 = load_config(no_github=True, concurrency=1)
    fake_c1 = FakeLLM(delay_seconds=0.1)

    t0 = time.perf_counter()
    _, summary_c1 = await run_screening_pipeline(
        input_dir=resumes_dir,
        config=cfg_c1,
        llm_client=fake_c1,
    )
    time_c1 = time.perf_counter() - t0
    enrich_c1 = summary_c1.timings.get("enrichment_and_scoring_s", 0)

    # Run 2: Concurrency 4
    cfg_c4 = load_config(no_github=True, concurrency=4)
    fake_c4 = FakeLLM(delay_seconds=0.1)

    t1 = time.perf_counter()
    _, summary_c4 = await run_screening_pipeline(
        input_dir=resumes_dir,
        config=cfg_c4,
        llm_client=fake_c4,
    )
    time_c4 = time.perf_counter() - t1
    enrich_c4 = summary_c4.timings.get("enrichment_and_scoring_s", 0)

    speedup = enrich_c1 / enrich_c4 if enrich_c4 > 0 else 1.0

    print("=" * 60)
    print("CONCURRENCY BENCHMARK RESULTS (50 Resumes, 33 Eligible):")
    print(f"Concurrency 1 - Enrichment/Scoring: {enrich_c1:.3f}s (Total: {time_c1:.3f}s)")
    print(f"Concurrency 4 - Enrichment/Scoring: {enrich_c4:.3f}s (Total: {time_c4:.3f}s)")
    print(f"Speedup Factor on I/O stage: {speedup:.2f}x")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_benchmark())

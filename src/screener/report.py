"""Report generation: atomic write of results.json, summary.json, and terminal summary."""

import csv
import json
import os
from pathlib import Path
from typing import List, Optional
from screener.models import CandidateResult, BatchSummary


def write_reports_atomically(
    results: List[CandidateResult],
    summary: BatchSummary,
    output_path: Path,
    summary_path: Optional[Path] = None,
    write_csv: bool = False,
) -> None:
    """
    Atomically write results.json and summary.json using temp files and os.replace.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if summary_path is None:
        summary_path = output_path.parent / "summary.json"

    # 1. Write results.json atomically
    tmp_results = output_path.with_suffix(f".tmp.{os.getpid()}")
    try:
        data = [r.model_dump(exclude_none=True) for r in results]
        with open(tmp_results, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_results, output_path)
    except Exception:
        if tmp_results.exists():
            tmp_results.unlink()
        raise

    # 2. Write summary.json atomically
    tmp_summary = summary_path.with_suffix(f".tmp.{os.getpid()}")
    try:
        with open(tmp_summary, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, indent=2)
        os.replace(tmp_summary, summary_path)
    except Exception:
        if tmp_summary.exists():
            tmp_summary.unlink()
        raise

    # 3. Optional CSV report
    if write_csv:
        csv_path = output_path.with_suffix(".csv")
        tmp_csv = csv_path.with_suffix(f".tmp.{os.getpid()}")
        try:
            with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Rank", "Candidate Name", "Email", "Status", "Total Score",
                    "AI Project Depth", "Python Backend", "Cloud Fullstack",
                    "GitHub", "Engineering Depth", "Source File"
                ])
                for r in results:
                    bd = r.score_breakdown
                    writer.writerow([
                        r.rank or "",
                        r.candidate_name or "",
                        r.email or "",
                        r.status,
                        r.total_score if r.total_score is not None else "",
                        bd.ai_project_depth if bd else "",
                        bd.python_backend if bd else "",
                        bd.cloud_fullstack if bd else "",
                        bd.github if bd else "",
                        bd.engineering_depth if bd else "",
                        r.source_file,
                    ])
            os.replace(tmp_csv, csv_path)
        except Exception:
            if tmp_csv.exists():
                tmp_csv.unlink()


def print_terminal_summary(
    results: List[CandidateResult],
    summary: BatchSummary,
    top_n: int = 5,
) -> None:
    """Print clean terminal report table with top-N candidates and summary metrics."""
    print("\n" + "=" * 70)
    print("AI RESUME SCREENING & RANKING BATCH SUMMARY")
    print("=" * 70)
    print(f"Total Files Found:      {summary.total_files}")
    print(f"Duplicates Skipped:     {summary.duplicates_skipped}")
    print(f"Unique Files Processed: {summary.unique_processed}")
    print(f"Successfully Parsed:    {summary.parsed}")
    print(f"Failed Files:           {summary.failed}")
    print(f"Eligible Candidates:    {summary.eligible}")
    print(f"Rejected Candidates:    {summary.rejected}")
    print("-" * 70)
    print("Timings:")
    for k, v in summary.timings.items():
        print(f"  - {k}: {v:.2f}s")
    print("-" * 70)

    # Top candidates table
    eligible = [r for r in results if r.status == "eligible"]
    print(f"\nTOP {min(top_n, len(eligible))} RANKED CANDIDATES:")
    header = f"{'Rank':<5} | {'Candidate Name':<22} | {'Score':<5} | {'AI':<3} | {'Py':<3} | {'Cld':<3} | {'GH':<3} | {'Eng':<3} | {'File'}"
    print(header)
    print("-" * len(header))

    for r in eligible[:top_n]:
        bd = r.score_breakdown
        ai = bd.ai_project_depth if bd else 0
        py = bd.python_backend if bd else 0
        cld = bd.cloud_fullstack if bd else 0
        gh = bd.github if bd else 0
        eng = bd.engineering_depth if bd else 0
        name = (r.candidate_name or "Unknown")[:20]
        score = str(r.total_score)
        print(f"#{r.rank:<4} | {name:<22} | {score:<5} | {ai:<3} | {py:<3} | {cld:<3} | {gh:<3} | {eng:<3} | {r.source_file}")

    print("=" * 70 + "\n")

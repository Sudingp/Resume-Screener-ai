"""Async pipeline orchestrating ingestion, parsing, eligibility, enrichment, scoring, and ranking."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple
from screener.config import AppConfig
from screener.errors import ParseError, ScreenerError
from screener.extract.contact import (
    extract_candidate_name,
    extract_email,
    extract_github,
)
from screener.github.client import GitHubClient
from screener.github.parse import parse_github_identity
from screener.ingest import discover_files, CandidateFile
from screener.lexicon import CompiledLexicons
from screener.eligibility import check_eligibility
from screener.llm.base import LLMClient
from screener.llm.cache import LLMCache
from screener.llm.grounding import validate_grounding
from screener.llm.prompts import PROMPT_VERSION, build_extraction_prompt
from screener.llm.schemas import SCHEMA_VERSION, ResumeExtraction
from screener.models import (
    CandidateResult,
    BatchSummary,
    ParsedDocument,
    GitHubResult,
)
from screener.parsers import parse_document
from screener.ranking import rank_candidates
from screener.scoring.github_score import score_github_profile
from screener.scoring.heuristic import extract_heuristic
from screener.scoring.scorer import compute_scores


async def process_eligible_candidate(
    candidate_file: CandidateFile,
    parsed_doc: ParsedDocument,
    matched_skills: List[str],
    compiled_lexicons: CompiledLexicons,
    config: AppConfig,
    llm_client: Optional[LLMClient],
    llm_cache: Optional[LLMCache],
    github_client: Optional[GitHubClient],
    llm_semaphore: asyncio.Semaphore,
    github_semaphore: asyncio.Semaphore,
) -> CandidateResult:
    """Process an eligible candidate concurrently with isolated error boundaries."""
    # 1. Contact extraction
    email = extract_email(parsed_doc.text)
    github_url, github_username = parse_github_identity(
        parsed_doc.text, parsed_doc.hyperlinks
    )
    name = extract_candidate_name(parsed_doc.text, candidate_file.filename)

    scoring_mode = "llm"
    warnings: List[str] = []

    # 2. LLM Extraction with Cache and Heuristic Fallback
    extraction: Optional[ResumeExtraction] = None

    if config.runtime.llm_enabled and llm_client is not None:
        async with llm_semaphore:
            # Check cache
            if llm_cache:
                extraction = llm_cache.get(
                    config.runtime.llm_model,
                    PROMPT_VERSION,
                    SCHEMA_VERSION,
                    parsed_doc.normalized_text_hash,
                )

            if extraction is None:
                try:
                    prompt = build_extraction_prompt(
                        parsed_doc.text, config.runtime.max_text_chars
                    )
                    extraction = await llm_client.extract(prompt)
                    if llm_cache and extraction:
                        llm_cache.set(
                            config.runtime.llm_model,
                            PROMPT_VERSION,
                            SCHEMA_VERSION,
                            parsed_doc.normalized_text_hash,
                            extraction,
                        )
                except Exception as e:
                    # Graceful degradation on LLM failure after retries
                    warnings.append(f"LLM extraction failed ({e}); fell back to heuristic mode")
                    extraction = None

    # Fallback to heuristic if LLM disabled or failed
    is_heuristic = False
    if extraction is None:
        is_heuristic = True
        scoring_mode = "heuristic"
        extraction = extract_heuristic(parsed_doc.text, compiled_lexicons)
        warnings.append("Scored using deterministic heuristic fallback (LLM disabled or unavailable)")
    else:
        # Validate grounding on LLM extraction
        extraction, grounding_warnings = validate_grounding(extraction, parsed_doc.text)
        warnings.extend(grounding_warnings)

    # 3. GitHub Enrichment
    github_res: Optional[GitHubResult] = None
    if not config.runtime.github_enabled:
        github_res = GitHubResult(status="disabled", activity_points=0, repo_points=0)
    elif not github_username:
        github_res = GitHubResult(status="no_profile", activity_points=0, repo_points=0)
    elif github_client is not None:
        async with github_semaphore:
            profile_data = await github_client.fetch_profile(github_username)
            github_res = score_github_profile(profile_data, config.scoring.github)
    else:
        github_res = GitHubResult(status="no_profile", activity_points=0, repo_points=0)

    # 4. Compute Scores
    total_score, breakdown, adjustments, evidence, strengths, concerns = compute_scores(
        extraction=extraction,
        github_result=github_res,
        scoring_config=config.scoring,
        is_heuristic=is_heuristic,
    )

    # Candidate Name override if LLM extracted a high-quality name
    final_name = extraction.candidate_name or name

    # Project summary
    proj_summary = None
    if extraction.projects:
        proj_summary = extraction.projects[0].summary

    return CandidateResult(
        candidate_name=final_name,
        email=email or extraction.email,
        source_file=candidate_file.filename,
        status="eligible",
        eligible=True,
        total_score=total_score,
        score_breakdown=breakdown,
        adjustments=adjustments,
        matched_skills=matched_skills,
        project_summary=proj_summary,
        evidence=evidence,
        github_summary=github_res.summary if github_res else None,
        github=github_res,
        strengths=strengths,
        concerns=concerns,
        scoring_mode=scoring_mode,  # type: ignore
        warnings=warnings,
    )


async def run_screening_pipeline(
    input_dir: Path,
    config: AppConfig,
    llm_client: Optional[LLMClient] = None,
    github_client: Optional[GitHubClient] = None,
    cache_dir: Optional[Path] = None,
) -> Tuple[List[CandidateResult], BatchSummary]:
    """Run full screening pipeline on input_dir."""
    start_total = time.perf_counter()
    timings: Dict[str, float] = {}

    compiled_lexicons = CompiledLexicons(config.lexicons)
    llm_cache = LLMCache(cache_dir=cache_dir) if config.runtime.llm_enabled else None

    # Step 1: File Discovery & Ingest
    t0 = time.perf_counter()
    all_files, unsupported_count = discover_files(
        input_dir, max_size_mb=config.runtime.max_file_size_mb
    )
    timings["discover_s"] = time.perf_counter() - t0

    total_files = len(all_files)
    duplicates_skipped = 0
    unique_files: List[CandidateFile] = []

    for f in all_files:
        if f.is_duplicate:
            duplicates_skipped += 1
        else:
            unique_files.append(f)

    # Step 2 & 3: Parse and Eligibility
    t1 = time.perf_counter()
    parsed_count = 0
    failed_results: List[CandidateResult] = []
    rejected_results: List[CandidateResult] = []
    eligible_pairs: List[Tuple[CandidateFile, ParsedDocument, List[str]]] = []

    for cfile in unique_files:
        try:
            doc = parse_document(
                cfile.path,
                max_pages=config.runtime.max_pdf_pages,
                max_size_mb=config.runtime.max_file_size_mb,
            )
            parsed_count += 1

            # Deterministic Eligibility Check
            elig = check_eligibility(doc.text, compiled_lexicons, config)

            if elig.eligible:
                eligible_pairs.append((cfile, doc, elig.matched_skills))
            else:
                name = extract_candidate_name(doc.text, cfile.filename)
                email = extract_email(doc.text)
                rejected_results.append(
                    CandidateResult(
                        candidate_name=name,
                        email=email,
                        source_file=cfile.filename,
                        status="rejected",
                        eligible=False,
                        rejection_reasons=elig.rejection_reasons,
                        matched_skills=elig.matched_skills,
                        warnings=elig.warnings,
                        github=GitHubResult(status="skipped_rejected", activity_points=0, repo_points=0),
                    )
                )

        except ParseError as pe:
            failed_results.append(
                CandidateResult(
                    source_file=cfile.filename,
                    status="failed",
                    eligible=None,
                    failure_reason=pe.reason,
                    warnings=[str(pe)],
                )
            )
        except Exception as e:
            failed_results.append(
                CandidateResult(
                    source_file=cfile.filename,
                    status="failed",
                    eligible=None,
                    failure_reason="parse_error",
                    warnings=[f"Unexpected error: {e}"],
                )
            )

    timings["parse_and_eligibility_s"] = time.perf_counter() - t1

    # Step 4: Concurrent Enrichment & Scoring for Eligible
    t2 = time.perf_counter()
    llm_semaphore = asyncio.Semaphore(config.runtime.llm_concurrency)
    github_semaphore = asyncio.Semaphore(config.runtime.github_concurrency)

    async def safe_process(cfile, doc, skills):
        try:
            return await process_eligible_candidate(
                candidate_file=cfile,
                parsed_doc=doc,
                matched_skills=skills,
                compiled_lexicons=compiled_lexicons,
                config=config,
                llm_client=llm_client,
                llm_cache=llm_cache,
                github_client=github_client,
                llm_semaphore=llm_semaphore,
                github_semaphore=github_semaphore,
            )
        except Exception as e:
            return CandidateResult(
                source_file=cfile.filename,
                status="failed",
                eligible=True,
                failure_reason="parse_error",
                warnings=[f"Enrichment failure: {e}"],
            )

    tasks = [safe_process(cf, d, s) for cf, d, s in eligible_pairs]
    eligible_results = await asyncio.gather(*tasks)
    timings["enrichment_and_scoring_s"] = time.perf_counter() - t2

    # Step 5: Rank candidates
    all_results = rank_candidates(list(eligible_results) + rejected_results + failed_results)
    timings["total_s"] = time.perf_counter() - start_total

    summary = BatchSummary(
        schema_version=SCHEMA_VERSION,
        total_files=total_files,
        duplicates_skipped=duplicates_skipped,
        unique_processed=len(unique_files),
        parsed=parsed_count,
        failed=len(failed_results),
        eligible=len(eligible_pairs),
        rejected=len(rejected_results),
        timings=timings,
    )

    return all_results, summary

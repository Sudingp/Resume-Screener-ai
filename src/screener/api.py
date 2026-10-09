"""FastAPI REST API endpoints for AI Resume Screening & Ranking System."""

import asyncio
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from screener.config import load_config
from screener.github.client import GitHubClient
from screener.llm import create_llm_client
from screener.models import SCHEMA_VERSION, CandidateResult, BatchSummary
from screener.parsers import parse_document
from screener.pipeline import run_screening_pipeline, process_eligible_candidate
from screener.ingest import CandidateFile, compute_file_sha256
from screener.lexicon import CompiledLexicons
from screener.eligibility import check_eligibility
from screener.ranking import rank_candidates
from screener.extract.contact import extract_candidate_name, extract_email


app = FastAPI(
    title="AI Resume Screening & Ranking API",
    description="Deterministic hard filtering, LLM evidence extraction, GitHub enrichment, and explainable ranking.",
    version=SCHEMA_VERSION,
)

# In-memory storage for latest batch run
_LATEST_RESULTS: List[CandidateResult] = []
_LATEST_SUMMARY: Optional[BatchSummary] = None


class ScreenBatchRequest(BaseModel):
    input_dir: str = Field(..., description="Directory path containing resumes to screen")
    concurrency: Optional[int] = Field(default=4, ge=1, le=16)
    no_llm: bool = Field(default=False, description="Use deterministic heuristic fallback instead of LLM")
    no_github: bool = Field(default=False, description="Disable GitHub enrichment")


class ScreenBatchResponse(BaseModel):
    message: str
    summary: BatchSummary
    top_candidates: List[CandidateResult]


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "schema_version": SCHEMA_VERSION}


@app.post("/screen", response_model=ScreenBatchResponse, tags=["Screening"])
async def screen_batch(req: ScreenBatchRequest) -> ScreenBatchResponse:
    """Screen an entire directory of resumes and return ranked results and batch summary."""
    global _LATEST_RESULTS, _LATEST_SUMMARY
    input_path = Path(req.input_dir)

    if not input_path.exists() or not input_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Input directory does not exist or is not a directory: {req.input_dir}",
        )

    config = load_config(
        no_llm=req.no_llm,
        no_github=req.no_github,
        concurrency=req.concurrency,
    )

    llm_client = None
    if config.runtime.llm_enabled:
        try:
            llm_client = create_llm_client(config)
        except Exception:
            llm_client = None

    github_client = None
    if config.runtime.github_enabled:
        github_client = GitHubClient(
            token=config.runtime.github_token,
            timeout_seconds=config.runtime.github_timeout_seconds,
        )

    results, summary = await run_screening_pipeline(
        input_dir=input_path,
        config=config,
        llm_client=llm_client,
        github_client=github_client,
    )

    _LATEST_RESULTS = results
    _LATEST_SUMMARY = summary

    top_eligible = [r for r in results if r.status == "eligible"][:5]

    return ScreenBatchResponse(
        message="Batch screening completed successfully",
        summary=summary,
        top_candidates=top_eligible,
    )


@app.get("/results", response_model=List[CandidateResult], tags=["Screening"])
def get_results(
    status_filter: Optional[str] = Query(None, description="Filter by status: eligible, rejected, failed")
) -> List[CandidateResult]:
    """Get the ranked candidate results from the latest batch run."""
    global _LATEST_RESULTS
    if not _LATEST_RESULTS:
        return []

    if status_filter:
        return [r for r in _LATEST_RESULTS if r.status == status_filter.lower()]

    return _LATEST_RESULTS


@app.post("/screen/file", response_model=CandidateResult, tags=["Screening"])
async def screen_single_file(
    file: UploadFile = File(...),
    no_llm: bool = Query(True, description="Default to fast deterministic heuristic for single file test"),
) -> CandidateResult:
    """Upload and screen a single resume file in real-time."""
    config = load_config(no_llm=no_llm, no_github=True)
    compiled_lexicons = CompiledLexicons(config.lexicons)

    # Save to temp file
    suffix = Path(file.filename or "resume.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        sha256 = compute_file_sha256(tmp_path)
        cfile = CandidateFile(
            path=tmp_path,
            filename=file.filename or "uploaded_resume.pdf",
            size_bytes=len(content),
            sha256=sha256,
        )

        doc = parse_document(tmp_path)
        elig = check_eligibility(doc.text, compiled_lexicons, config)

        if not elig.eligible:
            name = extract_candidate_name(doc.text, cfile.filename)
            email = extract_email(doc.text)
            return CandidateResult(
                candidate_name=name,
                email=email,
                source_file=cfile.filename,
                status="rejected",
                eligible=False,
                rejection_reasons=elig.rejection_reasons,
                matched_skills=elig.matched_skills,
                warnings=elig.warnings,
            )

        # Eligible candidate processing
        llm_sem = asyncio.Semaphore(1)
        gh_sem = asyncio.Semaphore(1)

        result = await process_eligible_candidate(
            candidate_file=cfile,
            parsed_doc=doc,
            matched_skills=elig.matched_skills,
            compiled_lexicons=compiled_lexicons,
            config=config,
            llm_client=None,
            llm_cache=None,
            github_client=None,
            llm_semaphore=llm_sem,
            github_semaphore=gh_sem,
        )
        return result
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

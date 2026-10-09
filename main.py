"""CLI entrypoint for AI Resume Screening & Ranking System.

No business logic in this module; orchestrates CLI arguments and triggers pipeline.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from screener.config import load_config, ConfigError
from screener.github.client import GitHubClient
from screener.llm import create_llm_client, FakeLLM
from screener.pipeline import run_screening_pipeline
from screener.report import write_reports_atomically, print_terminal_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Resume Screening & Ranking System (Hybrid deterministic + LLM witness)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Path to folder containing resumes (PDFs)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path to output results.json file",
    )
    parser.add_argument(
        "--config-dir",
        "-c",
        type=Path,
        default=None,
        help="Optional path to directory containing scoring.yaml and lexicons.yaml",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Maximum concurrent LLM and GitHub requests (default from env or 4)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM extraction and use deterministic heuristic fallback",
    )
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Disable GitHub public profile enrichment",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Custom disk cache directory",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of top candidates to display in the terminal summary table (default: 5)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also export results to CSV alongside results.json",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("screener.cli")

    # Validate input directory
    if not args.input.exists() or not args.input.is_dir():
        sys.stderr.write(f"Fatal Error: Input directory '{args.input}' does not exist or is not a directory.\n")
        sys.exit(2)

    # Load configuration
    try:
        config = load_config(
            config_dir=args.config_dir,
            no_llm=args.no_llm,
            no_github=args.no_github,
            concurrency=args.concurrency,
        )
    except ConfigError as ce:
        sys.stderr.write(f"Fatal Configuration Error: {ce}\n")
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"Fatal Error loading configuration: {e}\n")
        sys.exit(2)

    # Initialize clients
    llm_client = None
    if config.runtime.llm_enabled:
        try:
            llm_client = create_llm_client(config)
        except Exception as e:
            logger.warning(
                "Could not initialize live LLM client (%s). Defaulting to heuristic scoring fallback.",
                e,
            )
            llm_client = None

    github_client = None
    if config.runtime.github_enabled:
        github_client = GitHubClient(
            token=config.runtime.github_token,
            timeout_seconds=config.runtime.github_timeout_seconds,
        )

    # Execute async pipeline
    try:
        results, summary = asyncio.run(
            run_screening_pipeline(
                input_dir=args.input,
                config=config,
                llm_client=llm_client,
                github_client=github_client,
                cache_dir=args.cache_dir,
            )
        )
    except Exception as e:
        sys.stderr.write(f"Fatal Pipeline Error: {e}\n")
        sys.exit(2)

    # Write output files atomically
    try:
        write_reports_atomically(
            results=results,
            summary=summary,
            output_path=args.output,
            write_csv=args.csv,
        )
    except Exception as e:
        sys.stderr.write(f"Fatal Error writing report: {e}\n")
        sys.exit(2)

    # Print terminal report
    print_terminal_summary(results=results, summary=summary, top_n=args.top)
    sys.exit(0)


if __name__ == "__main__":
    main()

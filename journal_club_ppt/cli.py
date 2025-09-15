"""Command line interface for the journal club PowerPoint generator."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from requests import RequestException

from .content import build_presentation_plan
from .fetchers import (
    ArticleMetadata,
    CrossrefClient,
    load_metadata_from_file,
    save_metadata_to_file,
)
from .ppt_builder import COLOR_SCHEMES, create_presentation

LOGGER = logging.getLogger(__name__)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description="Generate a pharmacy journal club PowerPoint presentation from a DOI or title.",
    )
    parser.add_argument("--doi", help="Digital Object Identifier for the article.")
    parser.add_argument("--title", help="Title or keywords for the article search.")
    parser.add_argument("--metadata-file", help="Path to a JSON file with pre-fetched article metadata.")
    parser.add_argument("--presenter", default="PharmD Candidate", help="Presenter name and credentials.")
    parser.add_argument("--institution", help="Institution or rotation site to include on the title slide.")
    parser.add_argument("--output", default="journal_club_presentation.pptx", help="Output PowerPoint filename.")
    parser.add_argument("--style", choices=[scheme.name for scheme in COLOR_SCHEMES], help="Optional style name to use.")
    parser.add_argument("--seed", type=int, help="Random seed for reproducible styling and content selection.")
    parser.add_argument(
        "--save-metadata",
        dest="save_metadata",
        help="Path to save fetched metadata for offline reuse.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity for troubleshooting.",
    )

    args = parser.parse_args(argv)

    if not any([args.doi, args.title, args.metadata_file]):
        parser.error("Provide at least one of --doi, --title, or --metadata-file.")

    return args


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point for console scripts."""

    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s: %(message)s")

    try:
        metadata = load_metadata(args)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Failed to load article metadata: %s", exc)
        return 1

    plan = build_presentation_plan(
        metadata,
        presenter=args.presenter,
        institution=args.institution,
        seed=args.seed,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    create_presentation(
        plan=plan,
        output_path=str(output_path),
        author=args.presenter,
        seed=args.seed,
        style_name=args.style,
    )

    LOGGER.info("Saved presentation to %s", output_path.resolve())

    if args.save_metadata:
        save_metadata_to_file(metadata, args.save_metadata)
        LOGGER.info("Metadata saved to %s", Path(args.save_metadata).resolve())

    print(f"Presentation created: {output_path.resolve()}")
    return 0


def load_metadata(args: argparse.Namespace) -> ArticleMetadata:
    """Load metadata either from disk or remote APIs."""

    if args.metadata_file:
        LOGGER.info("Loading metadata from %s", args.metadata_file)
        return load_metadata_from_file(args.metadata_file)

    client = CrossrefClient()

    if args.doi:
        try:
            LOGGER.info("Fetching article metadata for DOI %s", args.doi)
            return client.fetch_by_doi(args.doi)
        except RequestException as exc:  # pragma: no cover - network required
            raise RuntimeError(f"Unable to retrieve metadata for DOI {args.doi}: {exc}") from exc
    if args.title:
        try:
            LOGGER.info("Searching article metadata for title '%s'", args.title)
            return client.fetch_by_title(args.title)
        except RequestException as exc:  # pragma: no cover - network required
            raise RuntimeError(f"Unable to retrieve metadata for title '{args.title}': {exc}") from exc

    raise RuntimeError("No valid metadata source provided.")


if __name__ == "__main__":
    sys.exit(main())

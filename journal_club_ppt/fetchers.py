"""Utilities for retrieving article metadata from public APIs."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "PharmJournalClub/1.0 "
    "(Language=Python;mailto=pharm-journal-club@example.com)"
)


@dataclass
class ArticleMetadata:
    """Normalized metadata for a journal article."""

    title: str
    journal: Optional[str]
    doi: Optional[str]
    publication_date: Optional[str]
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    url: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    article_type: Optional[str] = None
    publisher: Optional[str] = None
    subjects: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    @property
    def citation_text(self) -> str:
        """Return a simple citation string for reference slides."""

        author_part = ""
        if self.authors:
            if len(self.authors) == 1:
                author_part = self.authors[0]
            elif len(self.authors) == 2:
                author_part = " and ".join(self.authors)
            else:
                author_part = f"{self.authors[0]} et al."
        date_part = self.publication_date or "n.d."
        journal_part = self.journal or ""
        volume_issue = ""
        if self.volume:
            volume_issue = self.volume
            if self.issue:
                volume_issue = f"{volume_issue}({self.issue})"
        pages_part = self.pages or ""
        doi_part = f"doi:{self.doi}" if self.doi else ""
        parts = [part for part in [author_part, date_part, self.title, journal_part, volume_issue, pages_part, doi_part] if part]
        return ". ".join(parts)


class CrossrefClient:
    """Client for querying Crossref's public API."""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 10) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.setdefault("User-Agent", USER_AGENT)

    def fetch_by_doi(self, doi: str) -> ArticleMetadata:
        """Retrieve metadata using a DOI."""

        doi = doi.strip()
        if not doi:
            raise ValueError("DOI must not be empty")
        url = f"{self.BASE_URL}/{doi}"
        LOGGER.debug("Requesting Crossref metadata by DOI: %s", url)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        return self._parse_message(payload["message"])

    def fetch_by_title(self, title: str) -> ArticleMetadata:
        """Retrieve metadata for the best matching title."""

        query = title.strip()
        if not query:
            raise ValueError("Title must not be empty")
        params = {"query.bibliographic": query, "rows": 5}
        LOGGER.debug("Searching Crossref metadata by title: %s", query)
        response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("message", {}).get("items", [])
        if not items:
            raise LookupError(f"No Crossref records found for title '{title}'.")
        # Return the most complete record by preferring items with abstracts.
        items.sort(key=lambda item: (1 if item.get("abstract") else 0, item.get("score", 0)), reverse=True)
        return self._parse_message(items[0])

    def _parse_message(self, message: Dict[str, Any]) -> ArticleMetadata:
        """Convert a Crossref API message to :class:`ArticleMetadata`."""

        title_list = message.get("title") or [""]
        title = title_list[0].strip()
        journal_list = message.get("container-title") or []
        journal = journal_list[0].strip() if journal_list else None
        doi = message.get("DOI")
        abstract_raw = message.get("abstract")
        abstract = clean_html(abstract_raw) if abstract_raw else None
        authors = []
        for author in message.get("author", []):
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            full = " ".join(part for part in [given, family] if part)
            if full:
                authors.append(full)
        publisher = message.get("publisher")
        subjects = message.get("subject", [])
        references: List[str] = []
        for ref in message.get("reference", [])[:5]:
            text = ref.get("unstructured") or ref.get("article-title")
            if not text and ref.get("DOI"):
                text = f"doi:{ref['DOI']}"
            if text:
                references.append(clean_html(text))
        publication_date = extract_publication_date(message)
        keywords = list(dict.fromkeys(message.get("subject", [])))
        url = message.get("URL")
        volume = message.get("volume")
        issue = message.get("issue")
        pages = message.get("page")
        article_type = message.get("type")

        return ArticleMetadata(
            title=title or "Untitled Article",
            journal=journal,
            doi=doi,
            publication_date=publication_date,
            authors=authors,
            abstract=abstract,
            url=url,
            keywords=keywords,
            volume=volume,
            issue=issue,
            pages=pages,
            article_type=article_type,
            publisher=publisher,
            subjects=subjects,
            references=references,
        )


def extract_publication_date(message: Dict[str, Any]) -> Optional[str]:
    """Return a human-readable publication date."""

    for key in ("published-print", "published-online", "issued"):
        date_info = message.get(key)
        if not date_info:
            continue
        date_parts = date_info.get("date-parts")
        if not date_parts:
            continue
        parts = date_parts[0]
        if not parts:
            continue
        year = parts[0]
        month = parts[1] if len(parts) > 1 else None
        day = parts[2] if len(parts) > 2 else None
        date_components = [str(year)]
        if month:
            date_components.append(f"{int(month):02d}")
        if day:
            date_components.append(f"{int(day):02d}")
        return "-".join(date_components)
    return None


def clean_html(text: str) -> str:
    """Remove simple HTML tags from API strings."""

    if text is None:
        return ""
    # Remove leading and trailing whitespace and HTML entities.
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"&[a-zA-Z]+;", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def load_metadata_from_file(path: str) -> ArticleMetadata:
    """Load :class:`ArticleMetadata` from a JSON file."""

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return ArticleMetadata(**data)


def save_metadata_to_file(metadata: ArticleMetadata, path: str) -> None:
    """Save metadata to a JSON file for offline use."""

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(metadata.__dict__, handle, ensure_ascii=False, indent=2)

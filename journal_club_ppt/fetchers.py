"""Utilities for retrieving article metadata from public APIs."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

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
    abstract_sections: Dict[str, str] = field(default_factory=dict)
    mesh_terms: List[str] = field(default_factory=list)
    clinical_trial_identifiers: List[str] = field(default_factory=list)

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
        metadata = self._parse_message(payload["message"])
        enrich_metadata_with_pubmed(metadata, doi=doi)
        return metadata

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
        metadata = self._parse_message(items[0])
        enrich_metadata_with_pubmed(metadata, title=title)
        return metadata

    def _parse_message(self, message: Dict[str, Any]) -> ArticleMetadata:
        """Convert a Crossref API message to :class:`ArticleMetadata`."""

        title_list = message.get("title") or [""]
        title = title_list[0].strip()
        journal_list = message.get("container-title") or []
        journal = journal_list[0].strip() if journal_list else None
        doi = message.get("DOI")
        abstract_raw = message.get("abstract")
        abstract = clean_html(abstract_raw) if abstract_raw else None
        abstract_sections = extract_structured_sections(abstract) if abstract else {}
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
            abstract_sections=abstract_sections,
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


def extract_structured_sections(text: str) -> Dict[str, str]:
    """Split a structured abstract into labeled sections."""

    if not text:
        return {}

    pattern = re.compile(
        r"(?P<label>(?:[A-Z][A-Za-z/&\-]+)(?:\s+[A-Za-z][A-Za-z/&\-]+){0,5})\s*:",
    )
    sections: Dict[str, str] = {}
    matches = list(pattern.finditer(text))
    if not matches:
        return {}
    for index, match in enumerate(matches):
        label = match.group("label").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections[label] = content
    return sections


def load_metadata_from_file(path: str) -> ArticleMetadata:
    """Load :class:`ArticleMetadata` from a JSON file."""

    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    metadata = ArticleMetadata(**data)
    if metadata.abstract and not metadata.abstract_sections:
        metadata.abstract_sections = extract_structured_sections(metadata.abstract)
    return metadata


def save_metadata_to_file(metadata: ArticleMetadata, path: str) -> None:
    """Save metadata to a JSON file for offline use."""

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(metadata.__dict__, handle, ensure_ascii=False, indent=2)


@dataclass
class PubMedRecord:
    """Selected fields extracted from the PubMed XML response."""

    abstract_sections: Dict[str, str]
    keywords: List[str]
    mesh_terms: List[str]
    trial_identifiers: List[str]


class PubMedClient:
    """Client for retrieving structured article details from PubMed."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 10) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.setdefault("User-Agent", USER_AGENT)

    def fetch_article(self, doi: Optional[str] = None, title: Optional[str] = None) -> Optional[PubMedRecord]:
        """Fetch a PubMed article by DOI or title."""

        pmid = self._resolve_pmid(doi=doi, title=title)
        if not pmid:
            return None
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml",
            "tool": "journal_club_ppt",
            "email": "pharm-journal-club@example.com",
        }
        try:
            response = self.session.get(
                f"{self.BASE_URL}/efetch.fcgi",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network required
            LOGGER.debug("PubMed efetch failed: %s", exc)
            return None

        return self._parse_article_xml(response.text)

    def _resolve_pmid(self, doi: Optional[str], title: Optional[str]) -> Optional[str]:
        """Return a PubMed identifier matching the DOI or title."""

        search_terms = []
        if doi:
            search_terms.append(f"{doi}[AID]")
        if title:
            search_terms.append(f"{title}[Title]")
        for term in search_terms:
            params = {
                "db": "pubmed",
                "term": term,
                "retmode": "json",
                "retmax": 1,
                "tool": "journal_club_ppt",
                "email": "pharm-journal-club@example.com",
            }
            try:
                response = self.session.get(
                    f"{self.BASE_URL}/esearch.fcgi",
                    params=params,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:  # pragma: no cover - network required
                LOGGER.debug("PubMed esearch failed for term %s: %s", term, exc)
                continue
            ids = payload.get("esearchresult", {}).get("idlist", [])
            if ids:
                return ids[0]
        return None

    def _parse_article_xml(self, xml_text: str) -> Optional[PubMedRecord]:
        """Parse the relevant fields from the PubMed XML string."""

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            LOGGER.debug("Unable to parse PubMed XML: %s", exc)
            return None

        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        abstract_sections: Dict[str, str] = {}
        for abstract_text in article.findall(".//Abstract/AbstractText"):
            label = (
                abstract_text.attrib.get("Label")
                or abstract_text.attrib.get("NlmCategory")
                or "Abstract"
            )
            text = "".join(abstract_text.itertext()).strip()
            if text:
                abstract_sections[label] = text

        keyword_texts: List[str] = []
        for keyword_list in article.findall(".//KeywordList"):
            for keyword in keyword_list.findall("Keyword"):
                text = "".join(keyword.itertext()).strip()
                if text:
                    keyword_texts.append(text)

        mesh_terms: List[str] = []
        for mesh in article.findall(".//MeshHeading/DescriptorName"):
            text = "".join(mesh.itertext()).strip()
            if text:
                mesh_terms.append(text)

        trial_identifiers: List[str] = []
        for acc in article.findall(".//ClinicalTrialInformation/AccessionNumber"):
            text = "".join(acc.itertext()).strip()
            if text:
                trial_identifiers.append(text)

        return PubMedRecord(
            abstract_sections=abstract_sections,
            keywords=keyword_texts,
            mesh_terms=mesh_terms,
            trial_identifiers=trial_identifiers,
        )


def enrich_metadata_with_pubmed(
    metadata: ArticleMetadata,
    doi: Optional[str] = None,
    title: Optional[str] = None,
) -> None:
    """Augment Crossref metadata with additional details from PubMed."""

    client = PubMedClient()
    record = client.fetch_article(doi=doi or metadata.doi, title=title or metadata.title)
    if not record:
        return

    if record.abstract_sections:
        metadata.abstract_sections.update(record.abstract_sections)
        if not metadata.abstract:
            metadata.abstract = " ".join(record.abstract_sections.values())
    if record.keywords:
        combined = list(dict.fromkeys([*metadata.keywords, *record.keywords]))
        metadata.keywords = combined
    if record.mesh_terms:
        metadata.mesh_terms = list(dict.fromkeys([*metadata.mesh_terms, *record.mesh_terms]))
    if record.trial_identifiers:
        metadata.clinical_trial_identifiers = list(
            dict.fromkeys([*metadata.clinical_trial_identifiers, *record.trial_identifiers])
        )

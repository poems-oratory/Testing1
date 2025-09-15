"""Build slide outlines based on article metadata."""
from __future__ import annotations

from dataclasses import dataclass
import random
import re
import textwrap
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Sequence

if TYPE_CHECKING:  # pragma: no cover - imported for static typing only
    from .fetchers import ArticleMetadata
else:  # pragma: no cover - fallback for runtime without optional dependency
    ArticleMetadata = Any


@dataclass
class TitleSlideData:
    """Information needed for the title slide."""

    title: str
    subtitle_lines: List[str]
    footer_lines: List[str]


@dataclass
class ContentSlideData:
    """Represent the contents of a single slide."""

    title: str
    bullets: List[str]
    notes: Optional[str] = None


@dataclass
class PresentationPlan:
    """Full plan for the PowerPoint presentation."""

    title_slide: TitleSlideData
    slides: List[ContentSlideData]


SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def split_sentences(text: str) -> List[str]:
    """Split text into sentences with light normalization."""

    if not text:
        return []
    sanitized = text.replace("\n", " ")
    sanitized = re.sub(r"\s+", " ", sanitized)
    sentences = SENTENCE_SPLIT_REGEX.split(sanitized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def to_bullet(text: str, width: int = 120) -> str:
    """Format text as a bullet-friendly sentence fragment."""

    cleaned = text.strip()
    cleaned = cleaned.rstrip(". ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > width:
        cleaned = textwrap.shorten(cleaned, width=width, placeholder="…")
    return cleaned


def gather_sentences(
    sentences: Sequence[str],
    include_keywords: Optional[Iterable[str]] = None,
    exclude_keywords: Optional[Iterable[str]] = None,
    limit: int = 3,
) -> List[str]:
    """Return sentences that match keyword criteria."""

    include = [keyword.lower() for keyword in include_keywords or []]
    exclude = [keyword.lower() for keyword in exclude_keywords or []]
    matches: List[str] = []
    for sentence in sentences:
        normalized = sentence.lower()
        if include and not any(keyword in normalized for keyword in include):
            continue
        if exclude and any(keyword in normalized for keyword in exclude):
            continue
        matches.append(to_bullet(sentence))
        if len(matches) >= limit:
            break
    return matches


def ensure_bullets(existing: List[str], fallback_messages: Sequence[str], limit: int = 3) -> List[str]:
    """Ensure a bullet list contains content by appending fallback messages."""

    bullets = list(existing)
    for message in fallback_messages:
        if len(bullets) >= limit:
            break
        if message not in bullets:
            bullets.append(message)
    return bullets[:limit]


def build_presentation_plan(
    metadata: ArticleMetadata,
    presenter: str,
    institution: Optional[str] = None,
    seed: Optional[int] = None,
) -> PresentationPlan:
    """Create a full presentation plan based on metadata."""

    rng = random.Random(seed or hash(metadata.title) % 2**32)
    sentences = split_sentences(metadata.abstract or "")

    # Title slide data
    subtitle_lines = [presenter]
    if institution:
        subtitle_lines.append(institution)
    if metadata.journal:
        subtitle_lines.append(metadata.journal)
    if metadata.publication_date:
        subtitle_lines.append(f"Published: {metadata.publication_date}")
    elif metadata.publisher:
        subtitle_lines.append(metadata.publisher)

    footer_lines = []
    if metadata.doi:
        footer_lines.append(f"DOI: {metadata.doi}")
    if metadata.url:
        footer_lines.append(metadata.url)

    title_slide = TitleSlideData(
        title=metadata.title,
        subtitle_lines=subtitle_lines,
        footer_lines=footer_lines,
    )

    overview_bullets = [
        f"Authors: {format_authors(metadata.authors)}",
        f"Journal: {metadata.journal or 'Not listed'}",
        f"Article type: {format_article_type(metadata.article_type)}",
        f"Publication date: {metadata.publication_date or 'Not available'}",
    ]
    if metadata.doi:
        overview_bullets.append(f"DOI: {metadata.doi}")
    if metadata.keywords:
        overview_bullets.append(f"Keywords: {', '.join(metadata.keywords[:5])}")
    overview_slide = ContentSlideData(
        title="Article Snapshot",
        bullets=overview_bullets[:5],
        notes=metadata.citation_text,
    )

    background = gather_sentences(
        sentences,
        include_keywords=["background", "context", "introduction", "rationale"],
        limit=3,
    )
    if not background:
        background = [to_bullet(sentence) for sentence in sentences[:2]]
    background = ensure_bullets(
        background,
        [
            "Summarize disease state burden and unmet needs.",
            "Highlight why the study question matters for pharmacy practice.",
        ],
    )

    objectives = gather_sentences(
        sentences,
        include_keywords=["objective", "aim", "purpose", "goal", "evaluate", "assess"],
        limit=3,
    )
    objectives = ensure_bullets(
        objectives,
        [
            "Identify the primary and secondary objectives of the study.",
            "Clarify hypotheses and clinical questions being tested.",
        ],
    )

    design_bullets: List[str] = []
    if metadata.article_type:
        design_bullets.append(f"Design: {format_article_type(metadata.article_type)}")
    design_bullets.extend(
        gather_sentences(
            sentences,
            include_keywords=[
                "random",
                "double-blind",
                "prospective",
                "retrospective",
                "multicenter",
                "phase",
                "trial",
            ],
            limit=3,
        )
    )
    design_bullets = ensure_bullets(
        design_bullets,
        [
            "Specify trial phase, blinding, and control arms.",
            "Note study location(s) and setting (inpatient, outpatient, etc.).",
        ],
    )

    methods = gather_sentences(
        sentences,
        include_keywords=["method", "enroll", "conduct", "random", "assign", "protocol"],
        limit=3,
    )
    methods = ensure_bullets(
        methods,
        [
            "Describe screening, randomization, and data collection processes.",
            "Include dosing strategy and follow-up schedule.",
        ],
    )

    population = gather_sentences(
        sentences,
        include_keywords=["patient", "participants", "inclusion", "exclusion", "age", "baseline"],
        limit=3,
    )
    population = ensure_bullets(
        population,
        [
            "Summarize inclusion and exclusion criteria.",
            "Report sample size and demographic highlights.",
        ],
    )

    intervention = gather_sentences(
        sentences,
        include_keywords=["intervention", "treatment", "dose", "therapy", "comparator", "control"],
        limit=3,
    )
    intervention = ensure_bullets(
        intervention,
        [
            "Outline intervention and comparator arms including dosing.",
            "Clarify supportive care or concomitant medication policies.",
        ],
    )

    outcomes = gather_sentences(
        sentences,
        include_keywords=["primary", "secondary", "outcome", "endpoint", "measure"],
        limit=3,
    )
    outcomes = ensure_bullets(
        outcomes,
        [
            "Define primary efficacy endpoint.",
            "List key secondary endpoints and assessment tools.",
        ],
    )

    results_efficacy = gather_sentences(
        sentences,
        include_keywords=["result", "achieved", "improved", "reduced", "increase", "efficacy", "significant"],
        limit=4,
    )
    results_efficacy = ensure_bullets(
        results_efficacy,
        [
            "Summarize magnitude and direction of efficacy results.",
            "Include clinically meaningful statistics or effect sizes.",
        ],
        limit=4,
    )

    safety = gather_sentences(
        sentences,
        include_keywords=["adverse", "safety", "tolerability", "event", "toxicity", "serious"],
        limit=3,
    )
    safety = ensure_bullets(
        safety,
        [
            "Report frequency of serious and common adverse events.",
            "Compare discontinuation rates between arms.",
        ],
    )

    statistics = gather_sentences(
        sentences,
        include_keywords=["statistic", "p=", "p ", "confidence", "hazard", "odds", "regression"],
        limit=3,
    )
    statistics = ensure_bullets(
        statistics,
        [
            "Identify statistical tests used for primary endpoint.",
            "Comment on power calculation and handling of missing data.",
        ],
    )

    clinical = gather_sentences(
        sentences,
        include_keywords=["clinical", "practice", "implication", "pharmac", "guideline"],
        limit=3,
    )
    clinical = ensure_bullets(
        clinical,
        [
            f"Assess how findings influence {metadata.journal or 'clinical'} practice.",
            "Discuss patient counseling and monitoring considerations.",
        ],
    )

    strengths = ensure_bullets(
        gather_sentences(
            sentences,
            include_keywords=["strength", "robust", "rigorous", "power"],
            limit=3,
        ),
        [
            "Appropriate study design and control measures.",
            "Clear definition of outcomes and standardized assessments.",
            "Relevant population for pharmacy learners.",
        ],
    )

    limitations = ensure_bullets(
        gather_sentences(
            sentences,
            include_keywords=["limit", "bias", "lack", "small", "single", "confound"],
            limit=3,
        ),
        [
            "Consider selection bias and generalizability.",
            "Assess duration of follow-up and sample size adequacy.",
            "Note missing safety or adherence data.",
        ],
    )

    conclusion = gather_sentences(
        sentences,
        include_keywords=["conclude", "conclusion", "supports", "suggest", "indicate", "overall"],
        limit=3,
    )
    if not conclusion:
        conclusion = [to_bullet(sentence) for sentence in sentences[-2:]]
    conclusion = ensure_bullets(
        conclusion,
        [
            "State whether objectives were met and if results were clinically meaningful.",
            "Summarize recommendations for practice change or further research.",
        ],
    )

    discussion_questions = generate_discussion_questions(metadata, rng)

    reference_bullets = [metadata.citation_text]
    for ref in metadata.references[:3]:
        reference_bullets.append(to_bullet(ref))
    reference_bullets = ensure_bullets(
        reference_bullets,
        [
            "Include guideline or textbook references that contextualize therapy.",
            "Add institutional protocols or formulary notes as applicable.",
        ],
        limit=5,
    )

    slides = [
        overview_slide,
        ContentSlideData(title="Background", bullets=background),
        ContentSlideData(title="Study Objectives", bullets=objectives),
        ContentSlideData(title="Study Design", bullets=design_bullets),
        ContentSlideData(title="Methods & Setting", bullets=methods),
        ContentSlideData(title="Study Population", bullets=population),
        ContentSlideData(title="Intervention & Comparator", bullets=intervention),
        ContentSlideData(title="Outcomes", bullets=outcomes),
        ContentSlideData(title="Results – Efficacy", bullets=results_efficacy),
        ContentSlideData(title="Results – Safety", bullets=safety),
        ContentSlideData(title="Statistics & Data Integrity", bullets=statistics),
        ContentSlideData(title="Clinical Relevance", bullets=clinical),
        ContentSlideData(title="Strengths", bullets=strengths),
        ContentSlideData(title="Limitations", bullets=limitations),
        ContentSlideData(title="Conclusion", bullets=conclusion),
        ContentSlideData(title="Discussion Questions", bullets=discussion_questions),
        ContentSlideData(title="References", bullets=reference_bullets),
    ]

    return PresentationPlan(title_slide=title_slide, slides=slides)


def format_authors(authors: Sequence[str], limit: int = 4) -> str:
    """Format authors into a concise string."""

    if not authors:
        return "Not reported"
    if len(authors) <= limit:
        return ", ".join(authors)
    truncated = ", ".join(authors[:limit])
    return f"{truncated}, et al."


def format_article_type(article_type: Optional[str]) -> str:
    """Human-friendly description of the Crossref article type."""

    if not article_type:
        return "Not specified"
    article_type = article_type.replace("-", " ")
    return article_type.title()


def generate_discussion_questions(metadata: ArticleMetadata, rng: random.Random) -> List[str]:
    """Create a set of discussion questions tailored to the article."""

    topic = metadata.subjects[0] if metadata.subjects else metadata.keywords[0] if metadata.keywords else "clinical question"
    base_title = metadata.title.split(":")[0]
    prompts = [
        f"How do the study findings on {base_title.lower()} influence therapeutic decisions in {topic.lower()}?",
        "What patient factors would make you adopt or avoid the intervention from this study?",
        "What additional data would strengthen confidence in applying these results?",
        f"How do the outcomes compare with existing guidelines or standards of care in {topic.lower()}?",
        "What monitoring parameters should pharmacists prioritize based on this study?",
    ]
    rng.shuffle(prompts)
    return [to_bullet(prompt) for prompt in prompts[:3]]

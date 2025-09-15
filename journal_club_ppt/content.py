"""Build slide outlines based on article metadata."""
from __future__ import annotations

from dataclasses import dataclass
import random
import re
import textwrap
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence

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

SECTION_SYNONYMS = {
    "background": ["background", "importance", "context", "introduction", "rationale"],
    "objectives": ["objective", "objectives", "aim", "purpose", "research question", "goal"],
    "design": ["design", "study design", "trial design", "research design"],
    "methods": [
        "methods",
        "study methods",
        "patients and methods",
        "materials and methods",
        "design and methods",
    ],
    "results": ["results", "findings", "outcomes"],
    "conclusion": ["conclusion", "interpretation", "meaning", "discussion"],
    "safety": ["safety", "adverse", "harm"],
}


def split_sentences(text: str) -> List[str]:
    """Split text into sentences with light normalization."""

    if not text:
        return []
    sanitized = text.replace("\n", " ")
    sanitized = re.sub(r"\s+", " ", sanitized)
    sentences = SENTENCE_SPLIT_REGEX.split(sanitized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def normalize_label(label: str) -> str:
    """Normalize abstract section labels for comparison."""

    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def unique_preserve_order(items: Iterable[str]) -> List[str]:
    """Deduplicate items while preserving order."""

    seen = set()
    result: List[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def build_section_sentence_map(metadata: "ArticleMetadata") -> Dict[str, List[str]]:
    """Return a mapping of normalized section labels to sentence lists."""

    sections: Dict[str, List[str]] = {}
    for label, text in metadata.abstract_sections.items():
        normalized = normalize_label(label)
        if not normalized:
            continue
        sections[normalized] = split_sentences(text)
    return sections


def collect_section_sentences(
    section_map: Dict[str, List[str]],
    keywords: Sequence[str],
) -> List[str]:
    """Return sentences for section labels matching provided keywords."""

    normalized_keywords = [normalize_label(keyword) for keyword in keywords]
    sentences: List[str] = []
    for label, values in section_map.items():
        if any(keyword in label for keyword in normalized_keywords):
            sentences.extend(values)
    return sentences


def to_bullet(text: str, width: int = 120) -> str:
    """Format text as a bullet-friendly sentence fragment."""

    cleaned = text.strip()
    cleaned = cleaned.rstrip(". ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > width:
        cleaned = textwrap.shorten(cleaned, width=width, placeholder="…")
    return cleaned


def bullets_from_sentences(sentences: Iterable[str], limit: Optional[int] = None) -> List[str]:
    """Convert sentences into formatted bullet strings."""

    bullet_items = unique_preserve_order(to_bullet(sentence) for sentence in sentences)
    if limit is not None:
        return bullet_items[:limit]
    return bullet_items


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
    section_map = build_section_sentence_map(metadata)
    sentences = split_sentences(metadata.abstract or "")
    if not sentences and section_map:
        sentences = [sentence for values in section_map.values() for sentence in values]

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
    if metadata.mesh_terms:
        overview_bullets.append(f"MeSH terms: {', '.join(metadata.mesh_terms[:4])}")
    if metadata.clinical_trial_identifiers:
        overview_bullets.append(
            f"Trial registration: {', '.join(metadata.clinical_trial_identifiers[:2])}"
        )
    overview_slide = ContentSlideData(
        title="Article Snapshot",
        bullets=overview_bullets[:5],
        notes=metadata.citation_text,
    )

    background_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["background"])
    background = bullets_from_sentences(background_sentences, limit=3)
    if not background:
        background = gather_sentences(
            sentences,
            include_keywords=["background", "context", "introduction", "rationale"],
            limit=3,
        )
    if not background and sentences:
        background = bullets_from_sentences(sentences[:2], limit=2)
    background = ensure_bullets(
        background,
        [
            "Summarize disease state burden and unmet needs.",
            "Highlight why the study question matters for pharmacy practice.",
        ],
    )

    objective_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["objectives"])
    objectives = bullets_from_sentences(objective_sentences, limit=3)
    if not objectives:
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

    design_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["design"])
    if not design_sentences:
        design_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["methods"])
    design_bullets: List[str] = []
    if metadata.article_type:
        design_bullets.append(f"Design: {format_article_type(metadata.article_type)}")
    design_bullets.extend(bullets_from_sentences(design_sentences))
    if len(design_bullets) < 3:
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
                    "cohort",
                    "case-control",
                ],
                limit=3,
            )
        )
    design_bullets = ensure_bullets(
        unique_preserve_order(design_bullets),
        [
            "Specify trial phase, blinding, and control arms.",
            "Note study location(s) and setting (inpatient, outpatient, etc.).",
        ],
    )

    method_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["methods"])
    methods = bullets_from_sentences(method_sentences, limit=3)
    if not methods:
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
        method_sentences or sentences,
        include_keywords=["patient", "participants", "inclusion", "exclusion", "age", "baseline", "cohort"],
        limit=3,
    )
    if not population and method_sentences:
        population = bullets_from_sentences(method_sentences, limit=3)
    population = ensure_bullets(
        population,
        [
            "Summarize inclusion and exclusion criteria.",
            "Report sample size and demographic highlights.",
        ],
    )

    intervention = gather_sentences(
        method_sentences or sentences,
        include_keywords=["intervention", "treatment", "dose", "therapy", "comparator", "control", "regimen"],
        limit=3,
    )
    if not intervention and method_sentences:
        intervention = bullets_from_sentences(method_sentences, limit=3)
    intervention = ensure_bullets(
        intervention,
        [
            "Outline intervention and comparator arms including dosing.",
            "Clarify supportive care or concomitant medication policies.",
        ],
    )

    outcomes = gather_sentences(
        method_sentences or sentences,
        include_keywords=["primary", "secondary", "outcome", "endpoint", "measure"],
        limit=3,
    )
    if not outcomes and method_sentences:
        outcomes = bullets_from_sentences(method_sentences, limit=3)
    outcomes = ensure_bullets(
        outcomes,
        [
            "Define primary efficacy endpoint.",
            "List key secondary endpoints and assessment tools.",
        ],
    )

    result_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["results"])
    results_efficacy = gather_sentences(
        result_sentences or sentences,
        include_keywords=["result", "achieved", "improved", "reduced", "increase", "efficacy", "significant", "benefit"],
        limit=4,
    )
    if not results_efficacy and result_sentences:
        results_efficacy = bullets_from_sentences(result_sentences, limit=4)
    results_efficacy = ensure_bullets(
        results_efficacy,
        [
            "Summarize magnitude and direction of efficacy results.",
            "Include clinically meaningful statistics or effect sizes.",
        ],
        limit=4,
    )

    safety_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["safety"])
    safety_source = safety_sentences or result_sentences or sentences
    safety = gather_sentences(
        safety_source,
        include_keywords=["adverse", "safety", "tolerability", "event", "toxicity", "serious", "harm"],
        limit=3,
    )
    if not safety and safety_sentences:
        safety = bullets_from_sentences(safety_sentences, limit=3)
    safety = ensure_bullets(
        safety,
        [
            "Report frequency of serious and common adverse events.",
            "Compare discontinuation rates between arms.",
        ],
    )

    statistics_pool: List[str] = []
    if method_sentences:
        statistics_pool.extend(method_sentences)
    if result_sentences:
        statistics_pool.extend(result_sentences)
    if not statistics_pool:
        statistics_pool = list(sentences)
    statistics = gather_sentences(
        statistics_pool,
        include_keywords=["statistic", "p=", " p ", "confidence", "hazard", "odds", "regression", "ratio"],
        limit=3,
    )
    if not statistics and statistics_pool:
        statistics = bullets_from_sentences(statistics_pool, limit=3)
    statistics = ensure_bullets(
        statistics,
        [
            "Identify statistical tests used for primary endpoint.",
            "Comment on power calculation and handling of missing data.",
        ],
    )

    conclusion_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["conclusion"])

    clinical_source: List[str] = []
    if conclusion_sentences:
        clinical_source.extend(conclusion_sentences)
    if result_sentences:
        clinical_source.extend(result_sentences)
    if not clinical_source:
        clinical_source = list(sentences)
    clinical = gather_sentences(
        clinical_source,
        include_keywords=["clinical", "practice", "implication", "pharmac", "guideline", "management"],
        limit=3,
    )
    if not clinical and clinical_source:
        clinical = bullets_from_sentences(clinical_source, limit=3)
    clinical = ensure_bullets(
        clinical,
        [
            f"Assess how findings influence {metadata.journal or 'clinical'} practice.",
            "Discuss patient counseling and monitoring considerations.",
        ],
    )

    strengths_source: List[str] = []
    if conclusion_sentences:
        strengths_source.extend(conclusion_sentences)
    if method_sentences:
        strengths_source.extend(method_sentences)
    if not strengths_source:
        strengths_source = list(sentences)
    strengths = ensure_bullets(
        gather_sentences(
            strengths_source,
            include_keywords=["strength", "robust", "rigorous", "power", "strength"],
            limit=3,
        )
        or bullets_from_sentences(strengths_source, limit=3),
        [
            "Appropriate study design and control measures.",
            "Clear definition of outcomes and standardized assessments.",
            "Relevant population for pharmacy learners.",
        ],
    )

    limitations_source: List[str] = []
    if conclusion_sentences:
        limitations_source.extend(conclusion_sentences)
    if result_sentences:
        limitations_source.extend(result_sentences)
    if not limitations_source:
        limitations_source = list(sentences)
    limitations = ensure_bullets(
        gather_sentences(
            limitations_source,
            include_keywords=["limit", "bias", "lack", "small", "single", "confound", "harm", "uncertain"],
            limit=3,
        )
        or bullets_from_sentences(limitations_source, limit=3),
        [
            "Consider selection bias and generalizability.",
            "Assess duration of follow-up and sample size adequacy.",
            "Note missing safety or adherence data.",
        ],
    )

    conclusion = gather_sentences(
        conclusion_sentences or sentences,
        include_keywords=["conclude", "conclusion", "supports", "suggest", "indicate", "overall", "meaning"],
        limit=3,
    )
    if not conclusion and conclusion_sentences:
        conclusion = bullets_from_sentences(conclusion_sentences, limit=3)
    if not conclusion and sentences:
        conclusion = bullets_from_sentences(sentences[-2:], limit=2)
    conclusion = ensure_bullets(
        conclusion,
        [
            "State whether objectives were met and if results were clinically meaningful.",
            "Summarize recommendations for practice change or further research.",
        ],
    )

    discussion_questions = generate_discussion_questions(
        metadata,
        rng,
        method_sentences=method_sentences,
        result_sentences=result_sentences,
        conclusion_sentences=conclusion_sentences,
    )

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


def generate_discussion_questions(
    metadata: ArticleMetadata,
    rng: random.Random,
    *,
    method_sentences: Optional[Sequence[str]] = None,
    result_sentences: Optional[Sequence[str]] = None,
    conclusion_sentences: Optional[Sequence[str]] = None,
) -> List[str]:
    """Create a set of discussion questions tailored to the article."""

    topic = "clinical question"
    for candidates in (metadata.subjects, metadata.mesh_terms, metadata.keywords):
        if candidates:
            topic = candidates[0]
            break

    base_title = metadata.title.split(":")[0]

    def highlight(sentence_list: Optional[Sequence[str]]) -> Optional[str]:
        if not sentence_list:
            return None
        return to_bullet(sentence_list[0])

    method_highlight = highlight(method_sentences)
    result_highlight = highlight(result_sentences)
    conclusion_highlight = highlight(conclusion_sentences)

    prompts = [
        f"How do the study findings on {base_title.lower()} influence therapeutic decisions in {topic.lower()}?",
        "What patient factors would make you adopt or avoid the intervention from this study?",
        "What additional data would strengthen confidence in applying these results?",
        f"How do the outcomes compare with existing guidelines or standards of care in {topic.lower()}?",
        "What monitoring parameters should pharmacists prioritize based on this study?",
    ]

    if method_highlight:
        prompts.append(
            f"Does the described approach ({method_highlight}) create any barriers to real-world implementation?"
        )
    if result_highlight:
        prompts.append(
            f"How should pharmacists interpret the result that {result_highlight.lower()} when selecting therapy?"
        )
    if conclusion_highlight:
        prompts.append(
            f"Do you agree with the authors' interpretation that {conclusion_highlight.lower()}?"
        )

    rng.shuffle(prompts)
    return [to_bullet(prompt) for prompt in prompts[:3]]

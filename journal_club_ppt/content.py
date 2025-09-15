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
    layout: str = "bullet"
    callouts: Optional[List[str]] = None


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
    require_numeric: bool = False,
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
        if require_numeric and not any(ch.isdigit() for ch in sentence):
            continue
        matches.append(to_bullet(sentence))
        if len(matches) >= limit:
            break
    return matches


def numeric_highlights(
    sentences: Sequence[str],
    include_keywords: Optional[Iterable[str]] = None,
    limit: int = 2,
) -> List[str]:
    """Return short highlights that emphasize numeric data."""

    include = [keyword.lower() for keyword in include_keywords or []]
    highlights: List[str] = []
    for sentence in sentences:
        normalized = sentence.lower()
        if include and not any(keyword in normalized for keyword in include):
            continue
        if not any(ch.isdigit() for ch in sentence):
            continue
        bullet = to_bullet(sentence, width=80)
        if bullet in highlights:
            continue
        highlights.append(bullet)
        if len(highlights) >= limit:
            break
    return highlights


def join_for_notes(*sources: Sequence[str], limit: int = 6) -> Optional[str]:
    """Combine raw sentences into slide notes."""

    combined: List[str] = []
    for source in sources:
        for sentence in source:
            cleaned = sentence.strip()
            if not cleaned:
                continue
            if cleaned in combined:
                continue
            combined.append(cleaned)
            if len(combined) >= limit:
                break
        if len(combined) >= limit:
            break
    if not combined:
        return None
    return "\n".join(combined[:limit])


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

    topic_focus = (
        (metadata.mesh_terms[0] if metadata.mesh_terms else None)
        or (metadata.keywords[0] if metadata.keywords else None)
        or (metadata.subjects[0] if metadata.subjects else None)
        or metadata.title
    )

    agenda_bullets = [
        f"Context: {topic_focus.lower()} burden and guideline expectations.",
        f"Dive into {metadata.title.split(':')[0]} study design and endpoints.",
        "Interpret outcomes, safety, and pharmacist-focused applications.",
    ]

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

    guideline_source = background_sentences + sentences
    guideline = gather_sentences(
        guideline_source,
        include_keywords=["guideline", "standard", "recommend", "practice", "society"],
        limit=3,
    )
    if len(guideline) < 3 and metadata.references:
        for ref in metadata.references:
            formatted = to_bullet(ref)
            if formatted not in guideline:
                guideline.append(formatted)
            if len(guideline) >= 3:
                break
    guideline = ensure_bullets(
        guideline,
        [
            "Identify leading guidelines influencing therapy decisions.",
            "Highlight practice gaps that this study addresses.",
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

    baseline = gather_sentences(
        method_sentences or sentences,
        include_keywords=["baseline", "enrolled", "screened", "eligible", "mean age", "median"],
        limit=6,
        require_numeric=True,
    )
    if len(baseline) < 3:
        baseline.extend(
            gather_sentences(
                method_sentences or sentences,
                include_keywords=["baseline", "demographic", "inclusion", "exclusion"],
                limit=6 - len(baseline),
            )
        )
    baseline = ensure_bullets(
        unique_preserve_order(baseline),
        [
            "Clarify screening numbers and reasons for exclusion.",
            "Describe baseline comorbidities that influence therapy.",
            "Highlight adherence or risk stratification data.",
        ],
        limit=6,
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
        limit=4,
    )
    if not outcomes and method_sentences:
        outcomes = bullets_from_sentences(method_sentences, limit=4)
    outcomes = ensure_bullets(
        outcomes,
        [
            "Define primary efficacy endpoint.",
            "List key secondary endpoints and assessment tools.",
        ],
        limit=4,
    )

    result_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["results"])

    primary_results = gather_sentences(
        result_sentences or sentences,
        include_keywords=["primary", "target", "main", "endpoint"],
        limit=4,
        require_numeric=True,
    )
    if len(primary_results) < 2:
        primary_results.extend(
            gather_sentences(
                result_sentences or sentences,
                include_keywords=["result", "achieved", "improved", "reduced", "increase"],
                limit=4 - len(primary_results),
            )
        )
    primary_results = ensure_bullets(
        unique_preserve_order(primary_results),
        [
            "Summarize magnitude and direction of primary outcome results.",
            "State whether prespecified targets were met.",
        ],
        limit=4,
    )
    primary_callouts = numeric_highlights(
        result_sentences or sentences,
        include_keywords=["primary", "target", "endpoint"],
        limit=2,
    )

    secondary_results = gather_sentences(
        result_sentences or sentences,
        include_keywords=["secondary", "explor", "subgroup", "post-hoc"],
        limit=4,
        require_numeric=True,
    )
    if len(secondary_results) < 2:
        secondary_results.extend(
            gather_sentences(
                result_sentences or sentences,
                include_keywords=["additional", "benefit", "trend", "signal"],
                limit=4 - len(secondary_results),
            )
        )
    secondary_results = ensure_bullets(
        unique_preserve_order(secondary_results),
        [
            "Describe key secondary or exploratory findings.",
            "Highlight subgroup analyses relevant to pharmacists.",
        ],
        limit=4,
    )
    secondary_callouts = numeric_highlights(
        result_sentences or sentences,
        include_keywords=["secondary", "explor", "subgroup"],
        limit=2,
    )

    safety_sentences = collect_section_sentences(section_map, SECTION_SYNONYMS["safety"])
    safety_source = safety_sentences or result_sentences or sentences
    safety = gather_sentences(
        safety_source,
        include_keywords=["adverse", "safety", "tolerability", "event", "toxicity", "serious", "harm"],
        limit=3,
        require_numeric=True,
    )
    if not safety:
        safety = gather_sentences(
            safety_source,
            include_keywords=["adverse", "safety", "tolerability", "event", "toxicity", "serious", "harm"],
            limit=3,
        )
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

    recommendation = gather_sentences(
        clinical_source,
        include_keywords=["recommend", "implement", "adopt", "formulary", "collaborative", "pharmacist"],
        limit=3,
    )
    if not recommendation:
        recommendation = gather_sentences(
            conclusion_sentences or sentences,
            include_keywords=["support", "suggest", "indicate", "overall"],
            limit=3,
        )
    recommendation = ensure_bullets(
        recommendation,
        [
            "State a formulary or practice recommendation supported by study data.",
            "Describe monitoring and follow-up needed for implementation.",
            "Identify remaining questions for local policy makers.",
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

    key_data = gather_sentences(
        result_sentences or sentences,
        include_keywords=["percent", "mmhg", "ratio", "hazard", "risk", "difference", "change"],
        limit=6,
        require_numeric=True,
    )
    if len(key_data) < 3:
        key_data.extend(
            gather_sentences(
                result_sentences or sentences,
                include_keywords=["increase", "decrease", "improved", "reduced"],
                limit=6 - len(key_data),
                require_numeric=True,
            )
        )
    key_data = ensure_bullets(
        unique_preserve_order(key_data),
        [
            "Capture absolute risk reductions or number needed to treat.",
            "Highlight clinically meaningful changes with supporting numbers.",
            "Emphasize patient-centered outcomes or satisfaction metrics.",
        ],
        limit=6,
    )

    key_callouts = numeric_highlights(result_sentences or sentences, limit=3)

    slides = [
        overview_slide,
        ContentSlideData(title="Agenda", bullets=agenda_bullets, notes="Review flow for journal club."),
        ContentSlideData(title="Background", bullets=background, notes=join_for_notes(background_sentences, sentences)),
        ContentSlideData(
            title="Guideline & Practice Standards",
            bullets=guideline,
            notes=join_for_notes(guideline_source),
        ),
        ContentSlideData(title="Study Objectives", bullets=objectives, notes=join_for_notes(objective_sentences)),
        ContentSlideData(title="Study Design", bullets=design_bullets, notes=join_for_notes(design_sentences)),
        ContentSlideData(title="Methods & Setting", bullets=methods, notes=join_for_notes(method_sentences)),
        ContentSlideData(title="Study Population", bullets=population, notes=join_for_notes(method_sentences)),
        ContentSlideData(
            title="Baseline & Enrollment Data",
            bullets=baseline,
            layout="two-column",
            notes=join_for_notes(method_sentences),
        ),
        ContentSlideData(title="Intervention & Comparator", bullets=intervention, notes=join_for_notes(method_sentences)),
        ContentSlideData(title="Defined Outcomes", bullets=outcomes, notes=join_for_notes(method_sentences)),
        ContentSlideData(title="Statistics & Data Integrity", bullets=statistics, notes=join_for_notes(statistics_pool)),
        ContentSlideData(
            title="Primary Outcome Results",
            bullets=primary_results,
            notes=join_for_notes(result_sentences),
            callouts=primary_callouts,
        ),
        ContentSlideData(
            title="Secondary & Exploratory Results",
            bullets=secondary_results,
            notes=join_for_notes(result_sentences),
            callouts=secondary_callouts,
        ),
        ContentSlideData(title="Safety & Tolerability", bullets=safety, notes=join_for_notes(safety_source)),
        ContentSlideData(
            title="Key Data Highlights",
            bullets=key_data,
            notes=join_for_notes(result_sentences),
            layout="two-column",
            callouts=key_callouts,
        ),
        ContentSlideData(title="Clinical Relevance", bullets=clinical, notes=join_for_notes(clinical_source)),
        ContentSlideData(
            title="Implementation & Recommendation",
            bullets=recommendation,
            notes=join_for_notes(clinical_source, conclusion_sentences),
        ),
        ContentSlideData(title="Strengths", bullets=strengths, notes=join_for_notes(strengths_source)),
        ContentSlideData(title="Limitations", bullets=limitations, notes=join_for_notes(limitations_source)),
        ContentSlideData(title="Conclusion", bullets=conclusion, notes=join_for_notes(conclusion_sentences)),
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

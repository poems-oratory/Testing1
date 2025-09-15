# Journal Club PowerPoint Generator

This project provides a command-line tool that converts a DOI or article title into a fully structured PowerPoint presentation that meets the expectations of a fourth-year pharmacy student journal club.

The generator pulls bibliographic information from Crossref, builds a comprehensive slide outline, and then renders a styled PowerPoint deck with randomized themes so every run has a unique look.

## Features

- Accepts either a DOI, article title keywords, or a saved metadata JSON file.
- Retrieves article metadata (authors, journal, publication date, abstract, keywords, references) using the Crossref public API.
- Enriches metadata with PubMed when available to capture structured abstract sections, MeSH terms, and trial identifiers for
  evidence-based slide content.
- Automatically builds slides for agenda, guideline alignment, baseline characteristics, design, interventions, outcomes, primary/secondary results, safety, data highlights, clinical relevance, strengths, limitations, conclusion, discussion prompts, and references.
- Produces presenter notes, randomized visual accents, and numeric callout cards for key data that mirror high-quality journal club templates.
- Supports deterministic runs via `--seed`, multiple color schemes via `--style`, and offline reuse of metadata.

## Installation

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run the tool with either a DOI or title:

```bash
python -m journal_club_ppt.cli --doi 10.1056/NEJMoa2021436 --presenter "Alex Doe, PharmD Candidate" --institution "University Medical Center"
```

or

```bash
python -m journal_club_ppt.cli --title "Dapagliflozin in Patients with Chronic Kidney Disease" --output ckD_journal_club.pptx
```

### Helpful Options

- `--style`: choose a specific theme (`deep_ocean`, `sunset_copper`, `sage_green`, or `storm_gray`).
- `--seed`: reuse the same layout and sentence selection when regenerating the deck.
- `--metadata-file`: provide a JSON file created with `--save-metadata` for offline runs.
- `--save-metadata`: store fetched metadata for future use without another API call.
- `--log-level`: expose additional debugging output if an API call fails.

The finished presentation is saved to the path passed via `--output` (defaults to `journal_club_presentation.pptx`).

## Sample Offline Workflow

If network access is limited, first fetch metadata where connectivity is available:

```bash
python -m journal_club_ppt.cli --doi 10.1001/jama.2020.18717 --save-metadata remdesivir.json --output /tmp/dry_run.pptx
```

Later, reuse the JSON locally without additional API requests:

```bash
python -m journal_club_ppt.cli --metadata-file remdesivir.json --output remdesivir_journal_club.pptx
```

## Notes

- The planner extracts labeled sentences (Background, Methods, Results, Interpretation, etc.) from structured abstracts so
  slides highlight the same data a preceptor expects to hear.
- When abstracts lack specific sections, pharmacy-focused prompts are appended as gentle reminders to add local insight.
- Review the generated deck to tailor talking points for your site-specific expectations and add institution-specific
  recommendations when needed.

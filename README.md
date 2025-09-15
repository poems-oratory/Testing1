# Journal Club PowerPoint Generator

This project provides a command-line tool that converts a DOI or article title into a fully structured PowerPoint presentation that meets the expectations of a fourth-year pharmacy student journal club.

The generator pulls bibliographic information from Crossref, builds a comprehensive slide outline, and then renders a styled PowerPoint deck with randomized themes so every run has a unique look.

## Features

- Accepts either a DOI, article title keywords, or a saved metadata JSON file.
- Retrieves article metadata (authors, journal, publication date, abstract, keywords, references) using the Crossref public API.
- Automatically builds slides for background, objectives, design, methods, population, interventions, outcomes, efficacy, safety, statistics, clinical relevance, strengths, limitations, conclusion, discussion questions, and references.
- Produces slide notes and randomized visual accents appropriate for professional presentations.
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

- Crossref abstracts sometimes omit detailed results. The generator fills any gaps with pharmacy-focused prompts so the slides remain presentation-ready.
- Review the generated deck to tailor talking points for your site-specific expectations and add institution-specific recommendations when needed.

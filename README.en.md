中文说明：[README.md](README.md)

# Nature Impact — Academic Impact & Publication Intake (nature-impact)

[![Install](https://img.shields.io/badge/install-Codex%20%7C%20Claude%20Code%20%7C%20Antigravity%20%7C%20OpenClaw%20%7C%20OpenCode%20%7C%20Hermes-111827)](#multi-platform-installation--setup)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Nature Skills Family](https://img.shields.io/badge/ecosystem-Nature%20Skills-green.svg)](https://github.com/Yuan1z0825/nature-skills)

> **`nature-impact`** (formerly `scholar-impact-scraper`) is the core academic impact evaluation, citation metrics, journal quartile/partition lookup, and publication portfolio management skill within the **Nature Skills Ecosystem**.

## What Problem It Solves

Researchers, research assistants, PIs, and research administrators often need to collect and reconcile the same scattered signals:
- Scholar publications, citation counts, h-index, and i10-index on **Google Scholar**;
- **Web of Science (WoS)** citation and non-self-citation metrics;
- **ORCID** official certified publication records;
- **Clarivate JCR** journal categories, impact factors (IF), quartiles (Q1-Q4), and rankings;
- **CAS Journal Partitions** (Chinese Academy of Sciences) tiers and Top journal designations;
- Author order, first/corresponding-author verification, DOI and volume/issue/pages completion, and multi-format reference export including **GB/T 7714-2025**, APA, MLA, BibTeX, etc.

`nature-impact` turns these repetitive data workflows into standard Agent Skills and command-line automation, natively supporting **Codex, Claude Code, Antigravity, OpenClaw, OpenCode, Hermes**, and other AI coding assistants.

This project does not bypass platform access controls. Features requiring accounts or institutional subscriptions use your own authorized accounts or local credentials.

## Multi-Platform Installation & Setup

### 1. Codex

- **Global / Project Skill Installation**:
  ```bash
  # Windows PowerShell
  git clone https://github.com/bluessoul/nature-impact.git "$HOME\.codex\skills\nature-impact"

  # macOS / Linux
  git clone https://github.com/bluessoul/nature-impact.git ~/.codex/skills/nature-impact
  ```
  Or via `skills` CLI:
  ```bash
  npx skills add bluessoul/nature-impact --global --agent codex --skill nature-impact --yes --copy
  ```

### 2. Claude Code

- **Option A: Subagent Wrapper (Recommended)**
  Create `~/.claude/agents/nature-impact.md`:
  ```markdown
  ---
  name: nature-impact
  description: Academic impact evaluation, Google Scholar / WoS citation scraping, JCR quartiles, and CV publication intake
  ---
  You are an academic data expert. Follow `SKILL.md` and `AGENTS.md` strictly to collect and format scholar impact data.
  ```
  Call in Claude Code: `Use nature-impact subagent to summarize scholar impact data`.

- **Option B: Slash Command**
  Create `~/.claude/commands/nature-impact.md` and invoke with `/nature-impact`.

### 3. Antigravity (AGY)

- Place under Antigravity plugins or builtin skills:
  `~/.gemini/config/plugins/nature-skills/skills/nature-impact/` or `~/.gemini/antigravity/builtin/skills/nature-impact/`.
- Antigravity automatically indexes `SKILL.md` and routes queries regarding scholar impact, citations, WoS, h-index, and JCR partitions.

### 4. OpenClaw / QClaw

- Place under `~/.openclaw/skills/nature-impact/`. Environment variables declared in `metadata.openclaw` will be prompted and managed securely.

### 5. OpenCode & Hermes

- Place under `~/.opencode/skills/nature-impact/` or `~/.hermes/skills/nature-impact/` for native skill discovery and automated pipeline integration.


## Typical Use Cases

- **One-step CV/template import**: provide a `docx/pdf/txt/md` CV, a job/application template, or just a name plus affiliation; `scholar_intake.py` automatically identifies the scholar, publication clues, and requested fields, then produces readable local results.
- **Grant applications and CV preparation**: collect publications, citations, author order, corresponding-author signals, DOI, volume, issue, and pages, then export references in APA, MLA, Chicago, Harvard, LaTeX/BibTeX, AMA/Numeric, GB/T 7714, or GB/T 7714-2025.
- **Scholar impact screening**: quickly summarize Google Scholar and Web of Science citation signals for candidates, collaborators, lab members, or project teams.
- **Publication-list enrichment**: start from a Google Scholar profile, open detail panels to fill authors, journal/conference, volume, issue, pages, publisher, and DOI; use OpenAlex to enrich DOI, complete authors, corresponding authors, volume, issue, pages, source, and publisher; use Crossref only for DOI records still missing after those steps.
- **Journal selection and output reporting**: look up JCR quartiles, rankings, and impact factors, or use user-provided multi-year local JCR / CAS partition files as reference data for submission planning and annual reporting.
- **Agentic IDE workflows**: let Codex, Claude Code, OpenClaw, or similar clients read `SKILL.md`/`AGENTS.md` and help run local, human-in-the-loop research data workflows.

## Recent Updates

### 2026-06-21: One-step CV and template import

- Added `scholar_intake.py`: users can drop in a CV, an application template, or a name plus affiliation, and the tool automatically works out who to look up and what needs to be organized.
- Automatically recognizes name, affiliation, email, ORCID, Google Scholar ID, publication lists, and requested fields from the template, then creates a readable summary for the user.
- For Word files, it also tries to detect bold, underlined, and starred author markers so the user can confirm target, first, or corresponding authors. For PDFs, it warns that formatting is unreliable and asks for a Word file or extra author-role details.
- By default, the first run stops for review. After checking `final_summary.md`, rerun with `--yes` plus a year choice such as `--all-years`, `--year 2024`, or `--year-from 2020 --year-to 2024`. If affiliation, template requirements, year scope, or scholar identity are still unclear, the tool keeps asking for confirmation instead of organizing the wrong person.

### 2026-06: Metadata, citation-format, and partition enhancements

- Added `gbt2025` reference export for GB/T 7714-2025. The standard has been published and takes effect on 2026-07-01; the existing `gbt` output remains available for compatibility.
- `gbt2025` marks DOI-backed journal/conference records as `[J/OL]` or `[C/OL]` and writes DOI values as `DOI: 10.xxxx/...`.
- The interactive reference-format menu includes APA, MLA, Chicago, Harvard, LaTeX/BibTeX, AMA/Numeric, GB/T 7714, GB/T 7714-2025, and All.
- Default Scholar runs prefer DOI values from Google Scholar detail panels, then use OpenAlex for DOI, authors, corresponding authors, volume, issue, pages, source, and publisher, and only then use Crossref for records that still lack DOI.
- Use `--no-fetch-doi --no-openalex-enrich --no-fetch-corresponding` for a fast Google-Scholar-only run without metadata enrichment.

## What This Is

Scholar Impact Scraper is an academic impact extraction toolkit for QClaw/OpenClaw, Codex, Claude Code, Cloud Code, and other agentic IDEs. It can also be used as a normal command-line project.

It currently includes:

- One-step CV/template import for turning `docx/pdf/txt/md` CVs, application templates, or name-plus-affiliation input into automatically recognized scholar details, publication clues, requested fields, and readable local results.
- Google Scholar publication and citation scraping.
- OpenAlex structured metadata enrichment for DOI, complete authors, corresponding authors, source, publisher, volume, issue, and pages.
- Web of Science citation lookups when the user has legitimate access.
- ORCID publication extraction through the ORCID Public API.
- Clarivate JCR journal category, quartile, ranking, and impact-factor extraction.
- User-provided local CAS journal partition lookup from CSV, TSV, or JSON files.

## Before You Start

Make sure you have:

- Python 3.10 or newer.
- Node.js 18 or newer, including `npm`.
- Git.
- A desktop environment that can open a browser, because Playwright may need a visible browser for login or verification.

You do not need every account for every workflow. Configure only the credentials required by the feature you plan to use:

- ORCID: requires an ORCID Public API Client ID and Client Secret.
- OpenAlex: can be used anonymously; if you have an API key, configure it through `OPENALEX_API_KEY` or `--openalex-api-key` for more stable API access.
- Google Scholar: usually does not require an account, but may trigger verification or rate limits.
- Web of Science: requires legitimate institutional or personal access.
- Clarivate JCR: requires legitimate Clarivate/JCR access.

## Safety Rules

Do not commit, upload, paste, or publish:

- `.env`
- `.env.*` except `.env.example`
- `config.json`
- `.playwright_profile/`
- browser caches
- screenshots
- captured HTML pages
- generated CSV, JSON, Markdown, and log files

Treat `.playwright_profile/` as sensitive because it may contain cookies, login state, and institutional access traces.

If real credentials, tokens, or cookies were ever committed to Git history, deleting the file is not enough. Rotate or revoke the credential first, then clean the Git history.

## Install

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
npm install
```

macOS/Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
npm install
```

## Configure Local Credentials

Copy the environment template:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Then fill in only the values required by the workflow you plan to run:

```env
ORCID_CLIENT_ID=APP-XXXXXXXXXXXXXXXX
ORCID_CLIENT_SECRET=00000000-0000-0000-0000-000000000000
TARGET_ORCID_ID=0000-0002-1825-0097
OUTPUT_CSV=orcid_publications.csv

CLARIVATE_EMAIL=your_email@institution.edu
CLARIVATE_PASSWORD=your_password

OPENALEX_API_KEY=your_optional_openalex_api_key
```

Prefer `.env` or environment variables. `config.json` is supported only for local use, is ignored by Git, and must not be published.

## First Run: Save Browser Login State

If you plan to use live Web of Science or Clarivate/JCR lookup, it is recommended to save a local browser session first:

```bash
python launch_browser_for_login.py
```

On Windows, you can also run the JCR helper:

```powershell
.\launch_jcr_login.bat
```

Log in with an institutional or personal account that you are authorized to use, verify that the platform works, then close the browser. Login state is saved under `.playwright_profile/`. Treat this directory as sensitive and never commit or share it.

If you run a core script before `.playwright_profile/` exists, the script will remind you in the terminal and create `FIRST_RUN_LOGIN_SETUP.md` for Codex, Claude Code, OpenClaw, or similar clients to read. This reminder file is ignored by Git.

## Run A Smoke Test

Windows:

```powershell
.\.venv\Scripts\python tests\test_orcid_extractor.py
```

macOS/Linux:

```bash
./.venv/bin/python tests/test_orcid_extractor.py
```

If the test passes, your Python dependencies and base environment are working.

## Run ORCID Extraction

After configuring ORCID values in `.env`, run:

Windows:

```powershell
.\.venv\Scripts\python orcid_extractor.py
```

macOS/Linux:

```bash
./.venv/bin/python orcid_extractor.py
```

You can also override `.env` with command-line arguments:

```bash
python orcid_extractor.py --orcid 0000-0002-1825-0097 --client-id APP-YOURID --client-secret YOURSECRET --output my_publications.csv
```

## Run Google Scholar And Web Of Science

```bash
python scholar_playwright.py --user-id <Scholar_ID> --wos-id <WoS_ID> --output output.csv --max-clicks 5
```

Default runs now enable DOI resolution, OpenAlex enrichment, and corresponding-author lookup:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --max-clicks 5
```

This starts from Google Scholar list/detail extraction, then enriches records with OpenAlex, and finally uses Crossref only for records that still have no DOI. OpenAlex adds columns such as `OpenAlex ID`, `OpenAlex DOI`, `OpenAlex Authors`, `OpenAlex Author Count`, `OpenAlex Corresponding Authors`, `OpenAlex Source`, `OpenAlex Publisher`, `OpenAlex Volume`, `OpenAlex Issue`, `OpenAlex Pages`, and `OpenAlex Evidence JSON`.

To test a smaller number of records first:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --max-clicks 1 --openalex-max-records 20
```

For a fast Google-Scholar-only run without DOI/OpenAlex/corresponding-author enrichment:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --max-clicks 1 --no-fetch-doi --no-openalex-enrich --no-fetch-corresponding
```

Reference-format export:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --citation-format apa,gbt2025
```

Supported formats include `apa`, `mla`, `chicago`, `harvard`, `latex`/`bibtex`, `ama`, `gbt`, `gbt2025`, and `all`. CSV is always saved; reference files are generated as companion outputs. `gbt2025` targets GB/T 7714-2025 and marks DOI-backed online journal/conference records as `[J/OL]` or `[C/OL]` with `DOI: ...`.

You can export multiple formats in one run:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --citation-format apa,gbt,gbt2025
```

Target-author and corresponding-author marking:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --target-author "De-Yi Wang" --author-highlight both
```

`--target-author` or `--target-author-position` extracts the target author's position and highlights that author in author lists and reference exports. `--corresponding-author` or `--corresponding-author-position` can manually mark corresponding authors; the default corresponding-author lookup first reuses corresponding-author data from OpenAlex enrichment when available. Use `--no-fetch-corresponding` to disable it.

Output sorting is user-selectable:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --output output.csv --output-sort publication-date
```

`--output-sort` supports `citations`, `publication-date`, `year`, and `none`. The default remains `citations`, sorted by Google Scholar citation count descending. With `publication-date`, both CSV and reference exports use newest publications first.

If Web of Science needs institutional login, open a local persistent browser profile first:

```bash
python launch_browser_for_login.py
```

Log in manually in the browser window. After closing the browser, login state is stored locally in `.playwright_profile/`. Never commit or share that directory.

## Run JCR Extraction

### JCR / CAS Partition Data Sources

Partition lookup now supports three sources:

- Local CAS partition data: users provide their own files under `data/cas-local/`, or pass a file with `--local-partition-file`.
- Local JCR partition data: users provide their own JCR files under `data/jcr-local/`, or pass a file with `--local-partition-file`.
- Live JCR lookup: users with legitimate Clarivate/JCR access can use the Playwright browser workflow to query data visible to their account.

Live lookup does not bypass access control. You still need to use an institutional or personal account that you are authorized to use.

By default, the public release does not bundle complete JCR or CAS raw partition files. These files may be subject to copyright, database rights, platform terms, institutional licenses, or redistribution restrictions. For local-only use, place your own multi-year files under `data/jcr-local/`, `data/cas-local/`, or another local path. If you decide to publish a data file to GitHub, first confirm that the source allows public redistribution and document the year, source, license, download date, and checksum.

When no partition source is specified, interactive runs ask whether to use local CAS data, local JCR data, live JCR lookup, or skip partition lookup. Non-interactive automation defaults to live JCR lookup; pass `--partition-source cas-local` explicitly when CAS partition output is required.

Prepare an input file. See:

```text
examples/jcr_input.example.json
```

Input format:

```json
[
  {
    "journal_name_or_issn": "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "publication_year": 2021
  }
]
```

Run:

```bash
npm run fetch -- --input examples/jcr_input.example.json --output jcr_results.md
```

Use local CAS partition data:

```bash
npm run fetch -- --input examples/jcr_input.example.json --output cas_results.md --partition-source cas-local
npm run fetch -- --journal "Advanced Functional Materials" --year 2024 --output cas_results.md --partition-source cas-local --local-partition-file data/cas-local/cas_2024_partitions.csv
```

Use local JCR partition data:

```bash
npm run fetch -- --input examples/jcr_input.example.json --output jcr_local_results.md --partition-source jcr-local
```

For automated or unattended runs:

```bash
npm run fetch -- --input examples/jcr_input.example.json --output jcr_results.md --skip-offline-reminder
```

If you use Clarivate/JCR automatic login, configure credentials only through local `.env` or environment variables:

```powershell
$env:CLARIVATE_EMAIL="your_email@institution.edu"
$env:CLARIVATE_PASSWORD="your_password"
```

## Output Files

Common outputs include:

- `*.csv`
- `*.json`
- `*.md`
- `*.html`
- `*.png`
- `*.log`

These are local artifacts by default. Before sharing or committing them, manually check that they do not contain personal information, institutional access traces, account data, cookies, copyrighted page content, or data that should not be public.

## Agentic IDE Support

This repository is designed to be friendly to multiple coding agents and agentic IDEs:

- `SKILL.md`: for tools that support skill workflows.
- `AGENTS.md`: for general coding agents.
- `CLAUDE.md`: for Claude Code.
- `GEMINI.md`: for Gemini or other agent clients.
- `QUICKSTART.md`: shorter setup and run instructions.
- `SECURITY.md` and `RELEASE_CHECKLIST.md`: security and release checks.

## Compliance

Use this tool only with accounts, subscriptions, and data you are authorized to access. Respect the terms of service, rate limits, copyright restrictions, institutional policies, and privacy obligations of Google Scholar, Web of Science, Clarivate JCR, and ORCID.

## License

This project is licensed under the Apache License 2.0. Copyright © 2026 bluessoul. If you use, modify, or redistribute this project, keep the `LICENSE`, `NOTICE`, and copyright notice, and provide attribution to the original project.

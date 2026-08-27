# Agent Instructions

This repository is `nature-impact` (formerly `scholar-impact-scraper`), part of the Nature Skills academic tool suite.

Use these instructions when working in Codex, Claude Code, Antigravity, OpenClaw, OpenCode, Hermes, or any other agentic environment.

## Project Purpose

The project collects academic impact data from:

- Google Scholar
- Web of Science
- ORCID
- Clarivate JCR
- User-provided local CAS journal partition files

It combines Python scripts, Playwright browser automation, and a Node.js JCR / partition fetcher.

## Safety Rules

Never read aloud, print, commit, upload, or summarize real secrets from:

- `.env`
- `.env.*` except `.env.example`
- `config.json`
- `.playwright_profile/`
- browser caches
- generated screenshots or captured HTML pages

Treat `.playwright_profile/` as sensitive. It may contain cookies and institutional access state.

Generated CSV, JSON, HTML, Markdown, PNG, JPG, JPEG, and log files are local artifacts until the user explicitly approves sharing them.

## Setup

Python:

```bash
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt
./.venv/Scripts/python -m playwright install chromium
```

On macOS/Linux, use:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
```

Node:

```bash
npm install
```

## Common Commands

Run ORCID extraction:

```bash
python orcid_extractor.py
```

Run Google Scholar/Web of Science extraction:

```bash
python scholar_playwright.py --user-id <Scholar_ID> --wos-id <WoS_ID> --output output.csv --max-clicks 5
```

Open a local browser profile for institutional login:

```bash
python launch_browser_for_login.py
```

Run JCR / partition extraction:

```bash
npm run fetch -- --input examples/jcr_input.example.json --output jcr_results.md
```

If the user does not specify the partition system, ask whether they want local CAS partition data, local JCR data, live JCR lookup, or no partition lookup. Local CAS files should be user-provided CSV/TSV/JSON files under `data/cas-local/` or passed with `--local-partition-file`.

Run tests:

```bash
python tests/test_orcid_extractor.py
```

## Before Committing

Run:

```bash
rg -n -i "password|passwd|pwd|token|secret|api[_-]?key|client[_-]?secret|cookie|session|authorization|bearer|email|username|login"
rg -n -i "xiang|imdea|PFr\\+iW4Q|u8ZwRT4|carlos"
git status --short --ignored
```

Keyword matches in placeholders, docs, tests, and variable names are acceptable only after manual review.

Real credentials, cookies, browser profiles, account identifiers, generated research outputs, and captured pages are not acceptable.

## Notes For Agents

- Prefer small, explicit changes.
- Do not add generated outputs to Git.
- Do not create a real `.env` unless the user asks.
- Do not attempt institutional login without user approval.
- If a command needs network access to install dependencies, ask for scoped approval.

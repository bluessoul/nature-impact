---
name: nature-impact
description: >-
  Academic impact evaluation, scholar citation metrics (Google Scholar, Web of Science, ORCID),
  Clarivate JCR & CAS journal partition lookup, OpenAlex/Crossref metadata enrichment, and CV/grant
  template publication intake with GB/T 7714-2025 and multi-format citation export.
  Use when the user needs scholar citation analysis, h-index tracking, WoS citation/other-citation verification,
  journal JCR Q1-Q4 / CAS partitions, CV/resume publication parsing, or academic report generation.
  Also trigger on Chinese phrasings like 学术影响力、学者引用、WoS他引、H指数、JCR分区、中科院分区、简历成果提取、申报表成果整理、GB/T 7714排版.
version: 2.0.0
author: Antigravity / bluessoul
metadata:
  openclaw:
    requires:
      env:
        - ORCID_CLIENT_ID (optional)
        - ORCID_CLIENT_SECRET (optional)
        - CLARIVATE_EMAIL (optional)
        - CLARIVATE_PASSWORD (optional)
        - OPENALEX_API_KEY (optional)
---

# Nature Impact — Academic Impact & Publication Intake Router

Use this skill when the user needs to collect or reconcile academic impact data from Google Scholar, Web of Science, ORCID, Clarivate JCR, or user-provided local CAS journal partition files.

## One-Step User Workflow

Default to the easiest user path. The user should be able to provide a CV, a document template, a name plus affiliation, a Scholar/ORCID/WoS URL, or a rough publication list without knowing command-line flags.

### What The User Can Provide

- If the user provides a CV, resume, Word document, PDF, Markdown, HTML, or plain text profile, first extract the scholar's likely full name, name variants, current and past affiliations, email/domain hints, ORCID iD, Google Scholar URL or `user` ID, Web of Science ResearcherID, Scopus Author ID when present, publication list, journal names, years, DOI values, author order, and any requested output format already visible in the document.
- If the user provides only a name and institution, search for candidate author identities using the name plus affiliation. Prefer exact institutional matches, profile photos only as secondary context, email/domain matches, ORCID links, personal/lab pages, Google Scholar profiles, OpenAlex authors, and Web of Science/ResearcherID pages where legally accessible. When more than one credible candidate remains, show a short disambiguation table and ask the user to choose instead of guessing.
- If the user provides a Google Scholar profile URL or ID, run the Scholar workflow directly and infer the target author from the profile name unless the user specifies a different target author.
- If the user provides an ORCID iD, run ORCID extraction and reconcile ORCID works against Scholar/OpenAlex data when Scholar data is also available.
- If the user provides an existing formatted CV, application form, grant template, or Word document, inspect its structure before producing output. Reuse its headings, ordering, citation style, naming conventions, language, and table/list layout unless the user asks for a different format.
- If the output format is not inferable from the input document or request, ask one concise question about the desired final format. Good defaults are: `CV-ready publication list`, `grant/application impact summary`, `CSV + references`, or `full local evidence package`.

### Question Policy

- Do not ask the user for Scholar ID, ORCID iD, citation style, or output schema before checking whether they are already present or inferable from the provided material.
- Ask before proceeding only when identity matching is ambiguous, legal access or login is required, the requested source is unavailable, or the final output format cannot be inferred.
- When asking, ask the smallest useful question and continue with the rest of the workflow while waiting whenever possible.
- For `scholar_intake.py`, default to a review-first workflow: generate the detected summary first, continue only when the user reruns with `--yes`, and still block if affiliation, identity, or template/output requirements are incomplete.
- Before running source scraping, require an explicit publication-year choice. Accept `--all-years`, `--year <YYYY>`, or `--year-from <YYYY> --year-to <YYYY>`. If no year scope is provided or clearly detected from the document, block and ask the user whether to use all years or a specific range.
- When the input is Word, inspect run-level author formatting and surface bold, underlined, and starred author-like segments for user confirmation. When the input is PDF, warn that author formatting is unreliable and ask for a Word file or explicit author-role details.

### Default Execution Plan

1. Identify the target scholar and confidence level from the provided material.
2. Extract or discover stable identifiers: Google Scholar `user` ID, ORCID iD, Web of Science ResearcherID, OpenAlex author ID, DOI values, and institutional profile URLs.
3. Run the least invasive source first: user-provided publication list or ORCID, then Google Scholar, then OpenAlex/Crossref enrichment, then Web of Science or JCR only when the user has legal access and the task requires it.
4. Normalize titles, years, venues, DOI values, author lists, author position, corresponding-author evidence, citation counts, h-index, journal partitions, and JCR data into one working table.
5. Compare scraped records against the CV/template publication list. Flag missing, duplicated, mismatched, low-confidence, or possibly different-author records instead of silently merging them.
6. Produce the final user-facing result in the requested or inferred format, plus local machine-readable artifacts for audit.

### Output Contract

Unless the user requests something narrower, deliver:

- A short answer-first summary with the target scholar, matched identifiers, source coverage, record count, citation/h-index metrics when available, and any unresolved ambiguity.
- A cleaned publication list in the requested/template style, preserving author highlighting and author order when requested.
- A CSV table with enriched metadata and evidence columns.
- Citation exports in the requested style, or in the style detected from the provided document.
- A quality-control note listing records that need manual review, including low-confidence profile matches, missing DOI, uncertain corresponding author, duplicate titles, or source conflicts.

For "ready to submit" requests, prioritize a polished final document or paste-ready section over raw diagnostics. Keep the diagnostics available as a separate local artifact.

### Profile Match Evidence

When discovering an author profile from name plus affiliation, record why the match was accepted: matched affiliation text, email/domain, ORCID cross-link, personal/lab page link, publication-title overlap, coauthor overlap, and source URL. If the evidence is weak, label the candidate as `needs user confirmation`.

## Privacy And Secrets

- Never publish or commit `config.json`, `.env`, `.playwright_profile/`, generated CSV/JSON/HTML files, screenshots, or browser caches.
- Ask the user to provide credentials through local environment variables or local ignored files only.
- Treat `.playwright_profile/` as sensitive because it may contain cookies and institutional access state.
- Do not display passwords, access tokens, cookies, or full credential-bearing config files in chat.

## Python Tools

Install dependencies:

```bash
pip install -r {baseDir}/requirements.txt
playwright install chromium
```

Run Scholar/Web of Science extraction:

```bash
python {baseDir}/scholar_playwright.py --user-id <Scholar_ID> --wos-id <WoS_ID> --output <Output_CSV> --max-clicks <Max_Clicks>
```

For Google Scholar extraction, use DOI resolution, OpenAlex enrichment, and corresponding-author lookup by default. The script defaults to `--fetch-doi`, `--openalex-enrich`, and `--fetch-corresponding`; use `--no-fetch-doi`, `--no-openalex-enrich`, or `--no-fetch-corresponding` only for fast, offline, or minimal runs. Optional Web of Science flags include `--fetch-wos-ut` and `--no-wos-ut`.
Use `--refine auto` or `--refine all` to open Google Scholar detail panels and enrich rows with `Journal`, `Conference`, `Volume`, `Issue`, `Pages`, `Publisher`, `Description`, and raw `Scholar Detail Fields JSON` when those fields are visible.
DOI resolution is multi-source. DOI values visible in Google Scholar detail panels are used first. When `--fetch-doi` is enabled with the default `--refine auto`, the script opens Scholar detail panels up to `--refine-limit` before querying Crossref. Only records that still have no DOI are queried against Crossref by title. CSV output records `DOI Source`, `DOI Confidence`, and `DOI Evidence JSON` for downstream verification.
OpenAlex metadata enrichment is enabled by default before Crossref fallback. It uses DOI exact lookup when a DOI is already available, otherwise title search with confidence scoring. Optional controls are `--openalex-api-key` (or `OPENALEX_API_KEY`), `--openalex-max-records <N>`, and `--openalex-min-confidence <score>`. The enrichment can fill missing DOI, complete authors when Scholar authors are truncated, corresponding authors, source, publisher, volume, issue, and pages. CSV output adds `OpenAlex ID`, `OpenAlex DOI`, `OpenAlex Match Confidence`, `OpenAlex Match Method`, `OpenAlex Authors`, `OpenAlex Author Count`, `OpenAlex Corresponding Authors`, `OpenAlex Corresponding Author Positions`, `OpenAlex Source`, `OpenAlex Publisher`, `OpenAlex Volume`, `OpenAlex Issue`, `OpenAlex Pages`, `OpenAlex Evidence JSON`, `Metadata Enrichment Source`, and `Metadata Enrichment Confidence`.
CSV output is always saved. By default, the script asks whether to also export references as APA, MLA, Chicago, Harvard, LaTeX/BibTeX, AMA/Numeric, GB/T 7714, GB/T 7714-2025, or all formats. For automation, pass `--citation-format none`, `--citation-format apa`, `--citation-format gbt2025`, or comma-separated values such as `--citation-format apa,latex,gbt2025`.
Output sorting is user-selectable with `--output-sort citations`, `publication-date`, `year`, or `none`. The default remains `citations`; use `--output-sort publication-date` when the user wants newest publications first.
Use `--target-author "<Name>"` or `--target-author-position <N>` to add target-author columns (`Target Author Position`, `Target Author Matched Name`, `Highlighted Authors`) and highlight that author in reference exports. Highlight styles are `--author-highlight bold`, `underline`, `both`, or `none`.
Corresponding-author support has two layers. First, a user can provide `--corresponding-author "<Name>"` or `--corresponding-author-position <N>`, which takes priority. Second, default corresponding-author lookup reuses OpenAlex enrichment first and uses Crossref as a no-guess fallback when structured corresponding-author data is unavailable. CSV output adds `Corresponding Author Position`, `Corresponding Author Matched Name`, `Is Target Author Corresponding`, `Highlighted Corresponding Authors`, `Corresponding Evidence Source`, `Corresponding Confidence`, and `Corresponding Evidence JSON`.

Run ORCID extraction:

```bash
python {baseDir}/orcid_extractor.py
```

## Login Helper

If Web of Science or JCR requires institutional login, open a local persistent browser profile:

```bash
python {baseDir}/launch_browser_for_login.py
```

Keep the generated `.playwright_profile/` directory local.

## JCR Tools

Install Node dependencies:

```bash
npm install
```

Run JCR / partition extraction:

```bash
npm run fetch -- --input <Input_JSON_Path> --output <Output_MD_Path>
```

If the user does not clearly specify which partition system they want, ask whether they want local CAS partition data, local JCR data, live JCR lookup, or no partition lookup. For CAS partition lookup, instruct the user to place their own legally obtained CSV/TSV/JSON files under `data/cas-local/` or pass `--local-partition-file <path>`.

Common options:

```bash
npm run fetch -- --input <Input_JSON_Path> --output cas_results.md --partition-source cas-local
npm run fetch -- --input <Input_JSON_Path> --output jcr_local_results.md --partition-source jcr-local
npm run fetch -- --input <Input_JSON_Path> --output jcr_live_results.md --partition-source jcr-live
```

Input JSON format:

```json
[
  {
    "journal_name_or_issn": "1007-9211",
    "publication_year": 2022
  }
]
```

## Output Handling

Generated CSV, JSON, Markdown, HTML, and screenshot files should be considered local artifacts until reviewed and explicitly approved for sharing.

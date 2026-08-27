#!/usr/bin/env python3
"""
Google Scholar Profile Scraper (Playwright Async Version)
Extracts publication records defensively with non-headless human emulation and manual CAPTCHA recovery.
"""

import os
import re
import sys
import csv
import random
import asyncio
import logging
import argparse
import urllib.parse
import json
import requests
import pandas as pd
from playwright.async_api import async_playwright

def is_profile_likely_initialized(profile_dir: str) -> bool:
    return os.path.isdir(profile_dir) and bool(os.listdir(profile_dir))


def write_first_run_login_setup(profile_dir: str) -> None:
    artifact_path = os.path.join(os.getcwd(), "FIRST_RUN_LOGIN_SETUP.md")
    content = f"""# First Run Login Setup

This project uses a local Playwright profile to save browser login state.

Profile directory:

`{profile_dir}`

Recommended setup before live Web of Science lookup:

1. Run `python launch_browser_for_login.py`.
2. In the opened browser, log in with an institutional or personal account you are authorized to use.
3. Verify that Web of Science works for your target profile.
4. Close the browser window so cookies and session state are saved locally.

For Clarivate/JCR login, run `launch_jcr_login.bat`.

Do not commit or share `.playwright_profile/`, `.env`, or `config.json`.

Timestamp: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}
"""
    try:
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"First-run login setup artifact written to: {artifact_path}")
    except Exception as exc:
        logger.warning(f"Failed to write first-run login setup artifact: {exc}")


def remind_first_run_login_setup(profile_dir: str, uses_wos: bool) -> None:
    if os.getenv("SKIP_LOGIN_REMINDER") == "1":
        return
    if is_profile_likely_initialized(profile_dir):
        return

    print("\n" + "=" * 80)
    print("[First Run Login Setup]")
    print("No existing .playwright_profile was detected.")
    print("The script can continue, but Web of Science/JCR access may require a saved browser login.")
    print("")
    print("Recommended setup:")
    print("  - Web of Science: python launch_browser_for_login.py")
    print("  - JCR: launch_jcr_login.bat")
    print("")
    if uses_wos:
        print("Because --wos-id was provided, logging in once before extraction is recommended.")
    print("Do not commit or share .playwright_profile/.")
    print("=" * 80 + "\n")

    write_first_run_login_setup(profile_dir)


DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)

def normalize_title_for_match(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_bib_value(title).lower())

def title_similarity(left: str, right: str) -> float:
    left_norm = normalize_title_for_match(left)
    right_norm = normalize_title_for_match(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    shorter, longer = sorted([left_norm, right_norm], key=len)
    return len(shorter) / len(longer) if shorter and shorter in longer else 0.0

def extract_doi_from_text(text: str) -> str:
    text = clean_bib_value(text)
    if not text:
        return ""
    text = text.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "")
    match = DOI_PATTERN.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(".,;)")

def format_doi_url(doi: str) -> str:
    clean_doi = normalize_doi(doi)
    return f"https://doi.org/{clean_doi}" if clean_doi else "N/A"

def extract_doi_from_scholar_details(detail_fields: dict) -> dict:
    for label, value in detail_fields.items():
        combined = f"{label} {value}"
        doi = extract_doi_from_text(combined)
        if doi:
            return {
                "doi": format_doi_url(doi),
                "source": "Google Scholar detail",
                "confidence": "high" if "doi" in label.strip().lower() else "medium",
                "evidence": {"field": label, "value": value}
            }
    return {"doi": "N/A", "source": "N/A", "confidence": "none", "evidence": {}}

def fetch_doi_evidence_via_crossref(title: str) -> dict:
    """
    Queries Crossref API to find the DOI of a paper by its title (Option 2).
    Returns a structured evidence object with DOI, source, confidence, and match metadata.
    """
    if not title or title == "N/A":
        return {"doi": "N/A", "source": "Crossref", "confidence": "none", "evidence": {"error": "missing title"}}
        
    encoded_title = urllib.parse.quote_plus(title)
    url = f"https://api.crossref.org/works?query.title={encoded_title}&rows=1"
    headers = {
        "User-Agent": "ScholarScraper/1.0 (mailto:scholar_scraper@example.com)"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get("message", {}).get("items", [])
            if items:
                primary = items[0]
                doi = primary.get("DOI")
                if doi:
                    returned_title = (primary.get("title") or [""])[0]
                    score = title_similarity(title, returned_title)
                    confidence = "high" if score >= 0.92 else "medium" if score >= 0.75 else "low"
                    return {
                        "doi": format_doi_url(doi),
                        "source": "Crossref",
                        "confidence": confidence,
                        "evidence": {
                            "query_title": title,
                            "matched_title": returned_title,
                            "similarity": round(score, 3),
                            "crossref_score": primary.get("score"),
                            "publisher": primary.get("publisher"),
                            "issued": primary.get("issued")
                        }
                    }
        return {"doi": "N/A", "source": "Crossref", "confidence": "none", "evidence": {"query_title": title, "error": "no DOI returned"}}
    except Exception as e:
        logger.warning(f"Crossref lookup failed for '{title[:40]}...': {e}")
        raise

def fetch_doi_via_crossref(title: str) -> str:
    return fetch_doi_evidence_via_crossref(title).get("doi", "N/A")

from intake.openalex_client import (
    OpenAlexClient,
    get_default_openalex_client,
    OPENALEX_WORK_SELECT,
)

def openalex_get_works(params: dict, api_key: str = "") -> dict:
    client = OpenAlexClient(api_key=api_key) if api_key else get_default_openalex_client()
    results = client.get_works(params, select=params.get("select", OPENALEX_WORK_SELECT))
    return {"results": results}

def fetch_openalex_work_candidates(record: dict, api_key: str = "", client: OpenAlexClient = None) -> tuple:
    if client is None:
        client = OpenAlexClient(api_key=api_key) if api_key else get_default_openalex_client()
    doi = normalize_doi(record.get("DOI", ""))
    if doi:
        work = client.get_work_by_doi(doi, select=OPENALEX_WORK_SELECT)
        return ([work] if work else []), "doi"

    title = clean_bib_value(record.get("Title"))
    if not title:
        return [], "none"
    results = client.search_works_by_title(title, per_page=3, select=OPENALEX_WORK_SELECT)
    return results, "title"

def openalex_source(work: dict) -> tuple:
    source = ((work.get("primary_location") or {}).get("source") or {})
    source_name = clean_bib_value(source.get("display_name"))
    publisher = clean_bib_value(source.get("host_organization_name") or source.get("publisher") or source.get("host_organization"))
    return source_name or "N/A", publisher or "N/A"

def openalex_pages(work: dict) -> str:
    biblio = work.get("biblio") or {}
    first_page = clean_bib_value(biblio.get("first_page"))
    last_page = clean_bib_value(biblio.get("last_page"))
    if first_page and last_page and first_page != last_page:
        return f"{first_page}-{last_page}"
    return first_page or last_page or "N/A"

def parse_openalex_work(work: dict) -> dict:
    authorships = work.get("authorships") or []
    corresponding_ids = set(work.get("corresponding_author_ids") or [])
    authors = []
    corresponding_authors = []
    corresponding_positions = []
    for idx, authorship in enumerate(authorships, 1):
        author = authorship.get("author") or {}
        author_id = author.get("id", "")
        name = clean_bib_value(authorship.get("raw_author_name") or author.get("display_name"))
        if name:
            authors.append(name)
        if authorship.get("is_corresponding") is True or (author_id and author_id in corresponding_ids):
            if name:
                corresponding_authors.append(name)
                corresponding_positions.append(str(idx))

    biblio = work.get("biblio") or {}
    source_name, publisher = openalex_source(work)
    return {
        "id": clean_bib_value(work.get("id")) or "N/A",
        "doi": format_doi_url(work.get("doi") or (work.get("ids") or {}).get("doi")),
        "title": clean_bib_value(work.get("title") or work.get("display_name")),
        "year": clean_bib_value(work.get("publication_year")),
        "authors": ", ".join(authors) if authors else "N/A",
        "author_count": len(authors),
        "corresponding_authors": "; ".join(corresponding_authors) if corresponding_authors else "N/A",
        "corresponding_positions": "; ".join(corresponding_positions) if corresponding_positions else "N/A",
        "source": source_name,
        "publisher": publisher,
        "volume": clean_bib_value(biblio.get("volume")) or "N/A",
        "issue": clean_bib_value(biblio.get("issue")) or "N/A",
        "pages": openalex_pages(work),
        "raw": work,
    }

def score_openalex_match(record: dict, parsed: dict, method: str) -> float:
    if method == "doi":
        return 1.0
    title_score = title_similarity(record.get("Title", ""), parsed.get("title", ""))
    score = title_score
    record_year = clean_bib_value(record.get("Year") or record.get("Publication Date"))
    if record_year and parsed.get("year") and record_year[:4] == str(parsed.get("year"))[:4]:
        score += 0.04
    record_venue = clean_bib_value(record.get("Journal/Venue") or record.get("Journal") or record.get("Conference"))
    if record_venue and parsed.get("source") != "N/A":
        score += min(title_similarity(record_venue, parsed.get("source")), 1.0) * 0.04
    return min(score, 1.0)

def confidence_label(score: float) -> str:
    if score >= 0.92:
        return "high"
    if score >= 0.82:
        return "medium"
    if score > 0:
        return "low"
    return "none"

def has_value(value) -> bool:
    return bool(clean_bib_value(value))

def set_if_missing(record: dict, key: str, value) -> None:
    if has_value(value) and not has_value(record.get(key)):
        record[key] = value

def ensure_openalex_columns(record: dict) -> None:
    defaults = {
        "OpenAlex ID": "N/A",
        "OpenAlex DOI": "N/A",
        "OpenAlex Match Confidence": "none",
        "OpenAlex Match Method": "N/A",
        "OpenAlex Authors": "N/A",
        "OpenAlex Author Count": "N/A",
        "OpenAlex Corresponding Authors": "N/A",
        "OpenAlex Corresponding Author Positions": "N/A",
        "OpenAlex Source": "N/A",
        "OpenAlex Publisher": "N/A",
        "OpenAlex Volume": "N/A",
        "OpenAlex Issue": "N/A",
        "OpenAlex Pages": "N/A",
        "OpenAlex Evidence JSON": "{}",
        "Metadata Enrichment Source": "N/A",
        "Metadata Enrichment Confidence": "none",
    }
    for key, value in defaults.items():
        record.setdefault(key, value)

def apply_openalex_parsed_work(record: dict, parsed: dict, score: float, method: str, min_confidence: float = 0.82) -> None:
    label = confidence_label(score)
    record["OpenAlex ID"] = parsed["id"]
    record["OpenAlex DOI"] = parsed["doi"]
    record["OpenAlex Match Confidence"] = f"{score:.3f}"
    record["OpenAlex Match Method"] = method
    record["OpenAlex Authors"] = parsed["authors"]
    record["OpenAlex Author Count"] = parsed["author_count"] if parsed["author_count"] else "N/A"
    record["OpenAlex Corresponding Authors"] = parsed["corresponding_authors"]
    record["OpenAlex Corresponding Author Positions"] = parsed["corresponding_positions"]
    record["OpenAlex Source"] = parsed["source"]
    record["OpenAlex Publisher"] = parsed["publisher"]
    record["OpenAlex Volume"] = parsed["volume"]
    record["OpenAlex Issue"] = parsed["issue"]
    record["OpenAlex Pages"] = parsed["pages"]
    record["OpenAlex Evidence JSON"] = json.dumps({
        "method": method,
        "confidence": score,
        "confidence_label": label,
        "matched_title": parsed["title"],
        "matched_year": parsed["year"],
        "openalex_id": parsed["id"],
    }, ensure_ascii=False)

    if score < min_confidence:
        return

    record["Metadata Enrichment Source"] = "OpenAlex"
    record["Metadata Enrichment Confidence"] = label
    if not has_value(record.get("DOI")) and parsed["doi"] != "N/A":
        record["DOI"] = parsed["doi"]
        record["DOI Source"] = "OpenAlex"
        record["DOI Confidence"] = label
        record["DOI Evidence JSON"] = record["OpenAlex Evidence JSON"]
    if ("..." in str(record.get("Authors", "")) or not has_value(record.get("Authors"))) and parsed["authors"] != "N/A":
        record["Authors"] = parsed["authors"]
    if parsed["source"] != "N/A":
        set_if_missing(record, "Journal/Venue", parsed["source"])
        set_if_missing(record, "Journal", parsed["source"])
    set_if_missing(record, "Publisher", parsed["publisher"])
    set_if_missing(record, "Volume", parsed["volume"])
    set_if_missing(record, "Issue", parsed["issue"])
    set_if_missing(record, "Pages", parsed["pages"])

def enrich_record_with_openalex(record: dict, api_key: str = "", min_confidence: float = 0.82, client: OpenAlexClient = None) -> None:
    ensure_openalex_columns(record)
    try:
        candidates, method = fetch_openalex_work_candidates(record, api_key, client=client)
        if not candidates:
            record["OpenAlex Evidence JSON"] = json.dumps({"error": "no matching OpenAlex work", "method": method}, ensure_ascii=False)
            return

        parsed_candidates = []
        for work in candidates:
            parsed = parse_openalex_work(work)
            score = score_openalex_match(record, parsed, method)
            parsed_candidates.append((score, parsed))
        score, parsed = max(parsed_candidates, key=lambda item: item[0])
        apply_openalex_parsed_work(record, parsed, score, method, min_confidence=min_confidence)
    except Exception as exc:
        record["OpenAlex Evidence JSON"] = json.dumps({"error": str(exc)}, ensure_ascii=False)

def enrich_records_with_openalex_batch(
    records: list,
    api_key: str = "",
    min_confidence: float = 0.82,
    max_records: int = 0,
) -> None:
    """Enriches publication records via OpenAlex using batch DOI queries where possible, with title fallback."""
    if not records:
        return
    limit = max_records if max_records and max_records > 0 else len(records)
    target_records = records[:limit]
    client = OpenAlexClient(api_key=api_key) if api_key else get_default_openalex_client()

    # Step 1: Collect records with pre-existing DOIs for batch lookup
    doi_to_records: dict[str, list[dict]] = {}
    remaining_records: list[dict] = []

    for record in target_records:
        ensure_openalex_columns(record)
        doi = normalize_doi(record.get("DOI", ""))
        if doi:
            doi_to_records.setdefault(doi, []).append(record)
        else:
            remaining_records.append(record)

    if doi_to_records:
        logger.info(f"Batch querying OpenAlex for {len(doi_to_records)} distinct DOIs...")
        batch_works = client.batch_get_works_by_dois(list(doi_to_records.keys()))
        for doi, rec_list in doi_to_records.items():
            work = batch_works.get(doi)
            if work:
                parsed = parse_openalex_work(work)
                for record in rec_list:
                    apply_openalex_parsed_work(record, parsed, 1.0, "doi_batch", min_confidence=min_confidence)
            else:
                # DOI batch missed or not found, add to remaining for title fallback
                remaining_records.extend(rec_list)

    # Step 2: Fallback title search for remaining records
    if remaining_records:
        logger.info(f"Querying OpenAlex by title for {len(remaining_records)} remaining records...")
        for idx, record in enumerate(remaining_records, 1):
            title = record.get("Title", "")
            logger.info(f"[{idx}/{len(remaining_records)}] OpenAlex title search: '{title[:45]}...'")
            enrich_record_with_openalex(record, api_key=api_key, min_confidence=min_confidence, client=client)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

CITATION_FORMATS = ["apa", "mla", "chicago", "harvard", "latex", "ama", "gbt", "gbt2025"]
CITATION_FORMAT_LABELS = {
    "apa": "APA",
    "mla": "MLA",
    "chicago": "Chicago",
    "harvard": "Harvard",
    "latex": "LaTeX/BibTeX",
    "ama": "AMA/Numeric",
    "gbt": "GB/T 7714",
    "gbt2025": "GB/T 7714-2025",
}

def clean_bib_value(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text in ("", "N/A", "nan", "None") else text

def split_authors(authors: str) -> list:
    authors = clean_bib_value(authors)
    if not authors:
        return []
    delimiter = ";" if ";" in authors else ","
    return [part.strip() for part in authors.split(delimiter) if part.strip()]

def normalize_author_name(name: str) -> str:
    return re.sub(r"[\W_]+", "", clean_bib_value(name).lower(), flags=re.UNICODE)

def parse_author_position(position) -> int:
    try:
        parsed = int(position)
        return parsed if parsed > 0 else 0
    except (TypeError, ValueError):
        return 0

def first_author_position(value) -> int:
    for part in str(value or "").split(";"):
        parsed = parse_author_position(part.strip())
        if parsed:
            return parsed
    return 0

def find_target_author(authors: str, target_author: str = "", target_position: int = 0) -> tuple:
    names = split_authors(authors)
    if not names:
        return 0, ""
    position = parse_author_position(target_position)
    if 1 <= position <= len(names):
        return position, names[position - 1]
    query = normalize_author_name(target_author)
    if not query:
        return 0, ""
    for idx, name in enumerate(names, 1):
        normalized = normalize_author_name(name)
        if normalized and (query == normalized or query in normalized or normalized in query):
            return idx, name
    return 0, ""

def apply_author_highlight(text: str, highlight_style: str = "bold", output_style: str = "text") -> str:
    text = clean_bib_value(text)
    style = (highlight_style or "none").strip().lower()
    if not text or style in ("none", "no", "off"):
        return text
    if output_style == "latex":
        if style == "bold":
            return f"\\textbf{{{text}}}"
        if style == "underline":
            return f"\\underline{{{text}}}"
        if style == "both":
            return f"\\underline{{\\textbf{{{text}}}}}"
        return text
    if style == "bold":
        return f"**{text}**"
    if style == "underline":
        return f"<u>{text}</u>"
    if style == "both":
        return f"**<u>{text}</u>**"
    return text

def build_highlighted_authors(authors: str, target_position: int, highlight_style: str = "bold", output_style: str = "text") -> str:
    names = split_authors(authors)
    position = parse_author_position(target_position)
    if not names or not (1 <= position <= len(names)):
        return authors
    highlighted = []
    for idx, name in enumerate(names, 1):
        highlighted.append(apply_author_highlight(name, highlight_style, output_style) if idx == position else name)
    return ", ".join(highlighted)

def annotate_target_author(record: dict, target_author: str = "", target_position: int = 0, highlight_style: str = "bold") -> None:
    position, matched_name = find_target_author(record.get("Authors", ""), target_author, target_position)
    record["Target Author Query"] = clean_bib_value(target_author) or (str(target_position) if parse_author_position(target_position) else "N/A")
    record["Target Author Position"] = position if position else "N/A"
    record["Target Author Matched Name"] = matched_name or "N/A"
    record["Highlighted Authors"] = build_highlighted_authors(record.get("Authors", ""), position, highlight_style) if position else record.get("Authors", "N/A")

def normalize_doi(doi: str) -> str:
    text = clean_bib_value(doi)
    if not text:
        return ""
    match = DOI_PATTERN.search(text)
    if match:
        return match.group(0).rstrip(".,;)")
    text = re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"(?i)^doi:\s*", "", text)
    return text.strip().rstrip(".,;)")

def fetch_openalex_corresponding_authors(doi: str) -> dict:
    clean_doi = normalize_doi(doi)
    if not clean_doi:
        return {"source": "OpenAlex", "confidence": "none", "error": "missing DOI", "authors": []}
    doi_url = f"https://doi.org/{clean_doi}"
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"doi:{doi_url}",
        "select": "id,doi,authorships,corresponding_author_ids",
        "per-page": 1,
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return {"source": "OpenAlex", "confidence": "none", "error": "no matching OpenAlex work", "authors": []}
        work = results[0]
        corresponding_ids = set(work.get("corresponding_author_ids") or [])
        authors = []
        for idx, authorship in enumerate(work.get("authorships") or [], 1):
            author = authorship.get("author") or {}
            author_id = author.get("id", "")
            raw_name = authorship.get("raw_author_name") or author.get("display_name", "")
            if authorship.get("is_corresponding") is True or (author_id and author_id in corresponding_ids):
                authors.append({
                    "name": raw_name,
                    "position": idx,
                    "openalex_author_id": author_id,
                })
        if authors:
            return {"source": "OpenAlex", "confidence": "high", "error": "", "authors": authors}
        return {"source": "OpenAlex", "confidence": "none", "error": "OpenAlex work has no corresponding-author flag", "authors": []}
    except Exception as exc:
        return {"source": "OpenAlex", "confidence": "none", "error": str(exc), "authors": []}

def fetch_crossref_corresponding_authors(doi: str) -> dict:
    clean_doi = normalize_doi(doi)
    if not clean_doi:
        return {"source": "Crossref", "confidence": "none", "error": "missing DOI", "authors": []}
    url = f"https://api.crossref.org/works/{urllib.parse.quote(clean_doi, safe='')}"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return {"source": "Crossref", "confidence": "none", "error": "no structured corresponding-author field", "authors": []}
    except Exception as exc:
        return {"source": "Crossref", "confidence": "none", "error": str(exc), "authors": []}

def annotate_corresponding_author(record: dict, corresponding_author: str = "", corresponding_position: int = 0, highlight_style: str = "bold", fetch_auto: bool = False) -> None:
    manual_position, manual_name = find_target_author(record.get("Authors", ""), corresponding_author, corresponding_position)
    query = clean_bib_value(corresponding_author) or (str(corresponding_position) if parse_author_position(corresponding_position) else "N/A")
    record["Corresponding Author Query"] = query
    record["Corresponding Author Position"] = manual_position if manual_position else "N/A"
    record["Corresponding Author Matched Name"] = manual_name or "N/A"
    record["Is Target Author Corresponding"] = "N/A"
    record["Highlighted Corresponding Authors"] = record.get("Authors", "N/A")
    record["Corresponding Evidence Source"] = "Manual" if manual_position else "N/A"
    record["Corresponding Confidence"] = "user-specified" if manual_position else "none"
    record["Corresponding Evidence JSON"] = "{}"

    if manual_position:
        record["Highlighted Corresponding Authors"] = build_highlighted_authors(record.get("Authors", ""), manual_position, highlight_style)
    elif fetch_auto:
        openalex_names = clean_bib_value(record.get("OpenAlex Corresponding Authors"))
        openalex_positions = [
            parse_author_position(part.strip())
            for part in str(record.get("OpenAlex Corresponding Author Positions", "")).split(";")
            if parse_author_position(part.strip())
        ]
        if openalex_names and openalex_positions:
            record["Corresponding Author Position"] = "; ".join(str(pos) for pos in openalex_positions)
            record["Corresponding Author Matched Name"] = openalex_names
            record["Corresponding Evidence Source"] = "OpenAlex enrichment"
            record["Corresponding Confidence"] = record.get("Metadata Enrichment Confidence", "high")
            record["Corresponding Evidence JSON"] = record.get("OpenAlex Evidence JSON", "{}")
            highlighted = record.get("Authors", "N/A")
            for pos in openalex_positions:
                highlighted = build_highlighted_authors(highlighted, pos, highlight_style)
            record["Highlighted Corresponding Authors"] = highlighted
        else:
            evidence = fetch_openalex_corresponding_authors(record.get("DOI", ""))
            if not evidence.get("authors"):
                crossref_evidence = fetch_crossref_corresponding_authors(record.get("DOI", ""))
                evidence = {
                    "source": "OpenAlex; Crossref",
                    "confidence": "none",
                    "error": f"OpenAlex: {evidence.get('error', '')}; Crossref: {crossref_evidence.get('error', '')}",
                    "authors": [],
                }
            record["Corresponding Evidence JSON"] = json.dumps(evidence, ensure_ascii=False)
            if evidence.get("authors"):
                names = [author.get("name", "") for author in evidence["authors"] if author.get("name")]
                positions = []
                matched_positions = []
                for author in evidence["authors"]:
                    pos, matched_name = find_target_author(record.get("Authors", ""), author.get("name", ""), author.get("position", 0))
                    if pos:
                        matched_positions.append(pos)
                        positions.append(str(pos))
                record["Corresponding Author Position"] = "; ".join(positions) if positions else "N/A"
                record["Corresponding Author Matched Name"] = "; ".join(names) if names else "N/A"
                record["Corresponding Evidence Source"] = evidence.get("source", "OpenAlex")
                record["Corresponding Confidence"] = evidence.get("confidence", "high")
                if matched_positions:
                    highlighted = record.get("Authors", "N/A")
                    for pos in matched_positions:
                        highlighted = build_highlighted_authors(highlighted, pos, highlight_style)
                    record["Highlighted Corresponding Authors"] = highlighted

    target_position = parse_author_position(record.get("Target Author Position"))
    corr_positions = {
        parse_author_position(part)
        for part in str(record.get("Corresponding Author Position", "")).split(";")
        if parse_author_position(part)
    }
    if target_position and corr_positions:
        record["Is Target Author Corresponding"] = "Yes" if target_position in corr_positions else "No"

def author_last_first(author: str) -> str:
    parts = author.split()
    if len(parts) <= 1:
        return author
    return f"{parts[-1]}, {' '.join(parts[:-1])}"

def author_initials(author: str) -> str:
    parts = author.split()
    if len(parts) <= 1:
        return author
    initials = " ".join(f"{p[0]}." for p in parts[:-1] if p)
    return f"{parts[-1]}, {initials}".strip()

def format_author_list(authors: str, style: str, target_position: int = 0, highlight_style: str = "none") -> str:
    names = split_authors(authors)
    if not names:
        return ""
    if style == "mla":
        if len(names) == 1:
            formatted_name = author_last_first(names[0])
            return apply_author_highlight(formatted_name, highlight_style) if parse_author_position(target_position) == 1 else formatted_name
        first_author = author_last_first(names[0])
        if parse_author_position(target_position) == 1:
            first_author = apply_author_highlight(first_author, highlight_style)
        return f"{first_author}, et al."
    if style == "ama":
        compact = []
        for idx, name in enumerate(names[:6], 1):
            parts = name.split()
            if len(parts) <= 1:
                formatted_name = name
            else:
                formatted_name = parts[-1] + "".join(p[0] for p in parts[:-1] if p)
            compact.append(apply_author_highlight(formatted_name, highlight_style) if idx == parse_author_position(target_position) else formatted_name)
        if len(names) > 6:
            compact.append("et al")
        return ", ".join(compact)
    if style in ("gbt", "gbt2025"):
        visible_names = []
        for idx, name in enumerate(names[:3], 1):
            visible_names.append(apply_author_highlight(name, highlight_style) if idx == parse_author_position(target_position) else name)
        suffix = ", 等" if len(names) > 3 else ""
        return ", ".join(visible_names) + suffix
    formatted = [author_initials(name) for name in names]
    position = parse_author_position(target_position)
    if 1 <= position <= len(formatted):
        formatted[position - 1] = apply_author_highlight(formatted[position - 1], highlight_style)
    if len(formatted) == 1:
        return formatted[0]
    if style == "apa":
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]
    return ", ".join(formatted)

def get_publication_year(row: dict) -> str:
    pub_date = clean_bib_value(row.get("Publication Date"))
    year = clean_bib_value(row.get("Year"))
    source = pub_date or year
    match = re.search(r"\b(18|19|20)\d{2}\b", source)
    return match.group(0) if match else source

def get_venue(row: dict) -> str:
    return (
        clean_bib_value(row.get("Journal"))
        or clean_bib_value(row.get("Conference"))
        or clean_bib_value(row.get("Journal/Venue"))
    )

def join_parts(parts: list, separator: str = ". ") -> str:
    cleaned = [part.strip().rstrip(".") for part in parts if clean_bib_value(part)]
    return separator.join(cleaned) + ("." if cleaned else "")

def bibtex_key(row: dict, index: int) -> str:
    authors = split_authors(row.get("Authors", ""))
    first_author = re.sub(r"[^A-Za-z0-9]", "", authors[0].split()[-1]) if authors else "work"
    year = re.sub(r"\D", "", get_publication_year(row)) or "nd"
    title_word = ""
    for word in re.findall(r"[A-Za-z0-9]+", clean_bib_value(row.get("Title"))):
        if len(word) > 3:
            title_word = word
            break
    return f"{first_author}{year}{title_word or index}"

def format_gbt_source(venue: str, year: str, volume: str, issue: str, pages: str, style: str = "gbt") -> str:
    source = venue
    if year:
        source += f", {year}" if source else year
    if volume:
        source += f", {volume}"
        if issue:
            source += f"({issue})"
    elif issue:
        source += f"({issue})" if source else f"({issue})"
    if pages:
        source += f": {pages}"
    return source

def format_gbt_doi(doi: str) -> str:
    clean_doi = normalize_doi(doi)
    return f"DOI: {clean_doi}" if clean_doi else ""

def format_citation(row: dict, style: str, index: int, highlight_style: str = "none") -> str:
    title = clean_bib_value(row.get("Title"))
    target_position = parse_author_position(row.get("Target Author Position")) or first_author_position(row.get("Corresponding Author Position"))
    authors = format_author_list(row.get("Authors", ""), style, target_position, highlight_style)
    year = get_publication_year(row)
    venue = get_venue(row)
    volume = clean_bib_value(row.get("Volume"))
    issue = clean_bib_value(row.get("Issue"))
    pages = clean_bib_value(row.get("Pages"))
    publisher = clean_bib_value(row.get("Publisher"))
    doi = clean_bib_value(row.get("DOI"))
    if doi and not doi.lower().startswith(("http://", "https://")) and doi != "N/A":
        doi = f"https://doi.org/{doi}"

    volume_issue = volume + (f"({issue})" if issue else "")
    if style == "apa":
        venue_part = venue
        if volume_issue:
            venue_part += f", {volume_issue}" if venue_part else volume_issue
        if pages:
            venue_part += f", {pages}" if venue_part else pages
        return join_parts([authors, f"({year})" if year else "", title, venue_part, doi])
    if style == "mla":
        parts = [authors, f'"{title}"' if title else "", venue]
        tail = []
        if volume:
            tail.append(f"vol. {volume}")
        if issue:
            tail.append(f"no. {issue}")
        if publisher:
            tail.append(publisher)
        if year:
            tail.append(year)
        if pages:
            tail.append(f"pp. {pages}")
        return join_parts(parts + [", ".join(tail), doi])
    if style == "chicago":
        issue_part = f", no. {issue}" if issue else ""
        year_part = f" ({year})" if year else ""
        pages_part = f": {pages}" if pages else ""
        venue_part = f"{venue} {volume}{issue_part}{year_part}{pages_part}".strip()
        return join_parts([authors, f'"{title}"' if title else "", venue_part, publisher, doi])
    if style == "harvard":
        author_year = f"{authors} {year}" if authors and year else authors or year
        quoted_title = f"'{title}'" if title else ""
        tail = []
        if venue:
            tail.append(venue)
        if volume:
            tail.append(f"vol. {volume}")
        if issue:
            tail.append(f"no. {issue}")
        if pages:
            tail.append(f"pp. {pages}")
        if publisher:
            tail.append(publisher)
        if doi:
            tail.append(doi)
        return join_parts([author_year, quoted_title, ", ".join(tail)])
    if style == "ama":
        citation = f"{index}. "
        body = join_parts([authors, title], ". ")
        journal_bits = venue
        if year:
            journal_bits += f". {year}" if journal_bits else year
        if volume_issue:
            journal_bits += f";{volume_issue}"
        if pages:
            journal_bits += f":{pages}"
        return citation + join_parts([body, journal_bits, doi])
    if style in ("gbt", "gbt2025"):
        authors_gbt = format_author_list(row.get("Authors", ""), style, target_position, highlight_style)
        base_doc_type = "C" if clean_bib_value(row.get("Conference")) and not clean_bib_value(row.get("Journal")) else "J"
        doc_type = f"{base_doc_type}/OL" if style == "gbt2025" and doi else base_doc_type
        title_part = f"{title}[{doc_type}]" if title else ""
        source = format_gbt_source(venue, year, volume, issue, pages, style)
        doi_part = format_gbt_doi(doi) if style == "gbt2025" else doi
        return join_parts([authors_gbt, title_part, source, doi_part])
    if style == "latex":
        fields = {
            "title": title,
            "author": " and ".join(
                apply_author_highlight(name, highlight_style, "latex") if idx == target_position else name
                for idx, name in enumerate(split_authors(row.get("Authors", "")), 1)
            ),
            "journal": clean_bib_value(row.get("Journal")) or clean_bib_value(row.get("Journal/Venue")),
            "booktitle": clean_bib_value(row.get("Conference")),
            "year": year,
            "volume": volume,
            "number": issue,
            "pages": pages,
            "publisher": publisher,
            "doi": doi.replace("https://doi.org/", "") if doi else "",
        }
        entry_type = "inproceedings" if fields["booktitle"] and not fields["journal"] else "article"
        lines = [f"@{entry_type}{{{bibtex_key(row, index)},"]
        for key, value in fields.items():
            if value:
                lines.append(f"  {key} = {{{value}}},")
        lines[-1] = lines[-1].rstrip(",")
        lines.append("}")
        return "\n".join(lines)
    return ""

def resolve_citation_formats(citation_format: str) -> list:
    requested = (citation_format or "ask").strip().lower()
    if requested in ("", "ask"):
        if not sys.stdin.isatty():
            logger.info("Non-interactive terminal detected; skipping optional reference-format export.")
            return []
        print("\nReference-format export is optional. CSV will always be saved.")
        print("Choose citation output format(s):")
        print("  1. APA")
        print("  2. MLA")
        print("  3. Chicago")
        print("  4. Harvard")
        print("  5. LaTeX/BibTeX")
        print("  6. AMA/Numeric")
        print("  7. GB/T 7714")
        print("  8. GB/T 7714-2025")
        print("  9. All")
        choice = input("Enter numbers or names separated by commas, or press Enter to skip: ").strip().lower()
        if not choice:
            return []
        requested = choice
    if requested in ("none", "skip", "no"):
        return []
    requested = (
        requested.replace("gb/t 7714-2025", "gbt2025")
        .replace("gb/t7714-2025", "gbt2025")
        .replace("gb/t-7714-2025", "gbt2025")
    )
    tokens = [token.strip().lower() for token in re.split(r"[,;/\s]+", requested) if token.strip()]
    if "all" in tokens or "9" in tokens:
        return CITATION_FORMATS
    aliases = {
        "1": "apa",
        "2": "mla",
        "3": "chicago",
        "4": "harvard",
        "5": "latex",
        "bibtex": "latex",
        "tex": "latex",
        "6": "ama",
        "numeric": "ama",
        "ama/numeric": "ama",
        "7": "gbt",
        "gb": "gbt",
        "gbt7714": "gbt",
        "gb/t": "gbt",
        "gb/t7714": "gbt",
        "gb/t-7714": "gbt",
        "8": "gbt2025",
        "gbt2025": "gbt2025",
        "gbt-2025": "gbt2025",
        "gbt7714-2025": "gbt2025",
        "gb7714-2025": "gbt2025",
        "gb2025": "gbt2025",
    }
    formats = []
    for token in tokens:
        fmt = aliases.get(token, token)
        if fmt in CITATION_FORMATS and fmt not in formats:
            formats.append(fmt)
        else:
            logger.warning(f"Unknown citation format ignored: {token}")
    return formats

def write_citation_exports(records: list, output_csv: str, citation_format: str, highlight_style: str = "none") -> None:
    formats = resolve_citation_formats(citation_format)
    if not formats:
        return
    base_path, _ = os.path.splitext(output_csv)
    for fmt in formats:
        ext = "bib" if fmt == "latex" else "txt"
        output_path = f"{base_path}_{fmt}.{ext}"
        content = "\n\n".join(format_citation(row, fmt, idx, highlight_style) for idx, row in enumerate(records, 1))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content + ("\n" if content else ""))
        logger.info(f"{CITATION_FORMAT_LABELS[fmt]} citations saved to: {os.path.abspath(output_path)}")

def sort_output_dataframe(df: pd.DataFrame, sort_mode: str = "citations") -> pd.DataFrame:
    mode = (sort_mode or "citations").strip().lower().replace("_", "-")
    if mode == "none":
        return df
    if mode == "citations" and "Citations" in df.columns:
        return df.sort_values(by="Citations", ascending=False)
    if mode in ("publication-date", "date"):
        if "Publication Date" in df.columns:
            parsed = pd.to_datetime(df["Publication Date"], errors="coerce")
            return df.assign(_sort_publication_date=parsed).sort_values(
                by=["_sort_publication_date", "Year"],
                ascending=[False, False],
                na_position="last",
            ).drop(columns=["_sort_publication_date"])
        mode = "year"
    if mode == "year" and "Year" in df.columns:
        parsed_year = pd.to_numeric(df["Year"], errors="coerce")
        return df.assign(_sort_year=parsed_year).sort_values(
            by="_sort_year",
            ascending=False,
            na_position="last",
        ).drop(columns=["_sort_year"])
    return df

async def handle_captcha_if_needed(page) -> None:
    """
    Checks if Google has triggered a CAPTCHA or blocked the request (sorry page).
    If triggered, pauses execution until the user manually solves it in the opened browser.
    """
    # Google Scholar redirects to a URL containing "sorry/index" when a CAPTCHA is triggered
    sorry_selector = "iframe[src*='sorry']"
    
    while "sorry" in page.url or await page.is_visible(sorry_selector):
        print("\n" + "="*80)
        print("⚠️  [警告] 谷歌学术触发了人机验证码 (CAPTCHA) 阻断保护！")
        print("Google Scholar has triggered a CAPTCHA. The script is PAUSED.")
        print("请在弹出的浏览器窗口中【手动完成验证码验证】以恢复执行。")
        print("Please manually solve the CAPTCHA in the open Chromium browser window.")
        print("="*80 + "\n")
        
        # Log status every 5 seconds while waiting
        await asyncio.sleep(5)
        
    # Once solved, ensure the profile elements are visible before continuing
    try:
        await page.wait_for_selector("#gsc_prf", timeout=10000)
    except Exception:
        pass

async def handle_wos_captcha_if_needed(page) -> None:
    """
    Checks if Web of Science has triggered a security verification or bot block.
    Pauses execution until the user manually solves it in the opened browser window.
    """
    block_keywords = [
        "verify you are human", 
        "unusual activity", 
        "security check", 
        "机器人", 
        "验证码", 
        "unusual activity coming from your institution",
        "access denied",
        "strictly necessary cookies"
    ]
    
    logger.info("Checking if Web of Science has triggered security CAPTCHA or blocking...")
    while True:
        try:
            body_text = await page.locator("body").inner_text()
        except Exception as e:
            logger.warning(f"Failed to read page body text: {e}")
            body_text = ""
            
        body_text_lower = body_text.lower()
        is_blocked = any(kw.lower() in body_text_lower for kw in block_keywords)
        
        if not is_blocked:
            break
            
        logger.warning("="*80)
        logger.warning("⚠️  [警告] Web of Science 触发了安全验证 / 流量拦截保护！")
        logger.warning("Web of Science has triggered a security verification / BOT check.")
        logger.warning("请在弹出的浏览器窗口中【手动完成验证 / 点击同意Cookie】以恢复执行。")
        logger.warning("Please manually solve the verification / Accept Cookies in the open browser window.")
        logger.warning("="*80)
        
        await asyncio.sleep(5)
    logger.info("Web of Science security check passed or not detected. Proceeding...")

async def scrape_wos_citations(orcid_id: str, page, fetch_wos_ut: bool = False) -> dict:
    """
    Queries Web of Science public profile using Playwright to extract WoS citation counts
    and optional Accession Numbers.
    Returns a dictionary mapping {normalized_title: {"citations": citation_count, "accession_number": ut_number}}.
    """
    clean_id = orcid_id.strip().split('/')[-1]
    url = f"https://www.webofscience.com/wos/author/record/{clean_id}"
    logger.info(f"Navigating to Web of Science Profile: {url}...")
    
    wos_citations = {}
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Give some time for initial load or redirects
        await asyncio.sleep(5)
        
        # Check if initially blocked by Captcha or cookie overlay
        block_keywords = [
            "verify you are human", "unusual activity", "security check", 
            "机器人", "验证码", "unusual activity coming from your institution",
            "access denied", "strictly necessary cookies"
        ]
        
        try:
            body_text = await page.locator("body").inner_text()
        except Exception:
            body_text = ""
            
        was_blocked = any(kw.lower() in body_text.lower() for kw in block_keywords)
        
        if was_blocked:
            logger.warning("Web of Science profile page is BLOCKED initially. Entering CAPTCHA wait...")
            await handle_wos_captcha_if_needed(page)
            
            # Re-navigate to the original URL now that the session is authenticated and has cookies!
            logger.info(f"Re-navigating to Web of Science Profile after solving block: {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(6)
        else:
            logger.info("No initial Web of Science block detected. Proceeding...")
        logger.info("Waiting for Web of Science publication items to load...")
        
        # Dismiss onboarding 'Got it' overlay guide if visible
        try:
            got_it_btn = page.locator("button:has-text('Got it')")
            if await got_it_btn.count() > 0 and await got_it_btn.first.is_visible():
                logger.info("Found onboarding 'Got it' guide popup. Clicking to dismiss...")
                await got_it_btn.first.click()
                await asyncio.sleep(2)
        except Exception as e:
            logger.debug(f"Failed to dismiss onboarding guide: {e}")
            
        # Stepwise scroll down to trigger lazy loading of publications
        logger.info("Scrolling down step-by-step to trigger Web of Science publications lazy loading...")
        for scroll_offset in [800, 1600, 2400, 3200, 4000]:
            await page.evaluate(f"window.scrollTo(0, {scroll_offset})")
            # Dynamic buffer sleep
            await asyncio.sleep(2.0)
            
        try:
            await page.wait_for_selector("app-record, .publication-item, [class*='publication-item'], app-record-list-item", timeout=20000)
        except Exception:
            # Check for Captcha again if wait times out
            await handle_wos_captcha_if_needed(page)
            # Re-navigate if blocked again
            try:
                body_text2 = await page.locator("body").inner_text()
            except Exception:
                body_text2 = ""
            if any(kw.lower() in body_text2.lower() for kw in block_keywords):
                logger.info(f"Re-navigating to Web of Science Profile after solving secondary block: {url}...")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(6)
            
        # Extract author-level metrics (H-Index, Citations, 他引)
        wos_h_index = "N/A"
        wos_sum_cited = "N/A"
        wos_sum_cited_without_self = "N/A"
        try:
            logger.info("Extracting Web of Science author-level metrics (H-Index, Citations, 他引)...")
            descriptors = page.locator(".wat-author-metric-descriptor")
            desc_count = await descriptors.count()
            for i in range(desc_count):
                desc_el = descriptors.nth(i)
                desc_text = (await desc_el.inner_text()).strip()
                parent = desc_el.locator("..")
                value_el = parent.locator(".wat-author-metric")
                if await value_el.count() > 0:
                    val_text = (await value_el.nth(0).inner_text()).strip()
                    
                    sub_desc_el = parent.locator(".wat-author-metric-sub-descriptor")
                    sub_desc_text = ""
                    if await sub_desc_el.count() > 0:
                        sub_desc_text = (await sub_desc_el.inner_text()).strip().lower()
                    
                    if desc_text.lower() == "h-index":
                        wos_h_index = val_text
                    elif desc_text.lower() == "sum of times cited":
                        if "without self-citations" in sub_desc_text:
                            wos_sum_cited_without_self = val_text
                        else:
                            wos_sum_cited = val_text
            logger.info(f"Web of Science Metrics: H-Index={wos_h_index}, Citations={wos_sum_cited}, 他引={wos_sum_cited_without_self}")
        except Exception as e:
            logger.warning(f"Failed to extract Web of Science author metrics: {e}")

        # Get all publication cards
        items = await page.locator("app-record, .publication-item, [class*='publication-item'], app-record-list-item").all()
        logger.info(f"Located {len(items)} publication records on Web of Science page.")
        
        for item in items:
            try:
                # Title: Check primary audited selectors, then fallback
                title_el = item.locator("a.title, a.title-link, .publication-title")
                title = ""
                if await title_el.count() > 0:
                    title = (await title_el.nth(0).inner_text()).strip()
                
                # Citations: Check primary audited selectors, then fallback
                citations = 0
                citations_el = item.locator("a[data-ta='stat-number-citation-related-count'], div.citations a.stat-number, .times-cited-value, [class*='times-cited']")
                if await citations_el.count() > 0:
                    cit_text = (await citations_el.nth(0).inner_text()).strip()
                    clean_cit = re.sub(r'\D', '', cit_text)
                    citations = int(clean_cit) if clean_cit else 0
                
                # WoS Accession Number (UT)
                ut_number = "N/A"
                if fetch_wos_ut:
                    links = await item.locator("a[href]").all()
                    for link in links:
                        href = await link.get_attribute("href")
                        if href:
                            match = re.search(r'WOS:[A-Z0-9]+', href, re.IGNORECASE)
                            if match:
                                ut_number = match.group(0).upper()
                                break
                
                if title:
                    # Normalize title (lowercase, alphanumeric only)
                    norm_title = re.sub(r'[^a-z0-9]', '', title.lower())
                    wos_citations[norm_title] = {
                        "citations": citations,
                        "accession_number": ut_number
                    }
                    logger.info(f"WoS Scraped: '{title[:45]}...' | Citations: {citations} | UT: {ut_number}")
            except Exception as e:
                logger.debug(f"Error parsing WoS item: {e}")
                
    except Exception as e:
        logger.error(f"Failed to scrape Web of Science citations: {e}")
        
    return {
        "citations_map": wos_citations,
        "h_index": wos_h_index,
        "sum_cited": wos_sum_cited,
        "sum_cited_without_self": wos_sum_cited_without_self
    }

from intake.scholar_http_client import ScholarHttpClient, extract_scholar_user_id

async def scrape_scholar_profile(
    profile_url: str,
    output_csv: str,
    max_clicks: int,
    refine_mode: str = "auto",
    refine_limit: int = 10,
    fetch_doi: bool = True,
    wos_id: str = None,
    fetch_wos_ut: bool = False,
    citation_format: str = "ask",
    target_author: str = "",
    target_author_position: int = 0,
    author_highlight: str = "bold",
    corresponding_author: str = "",
    corresponding_author_position: int = 0,
    fetch_corresponding: bool = True,
    openalex_enrich: bool = True,
    openalex_api_key: str = "",
    openalex_max_records: int = 0,
    openalex_min_confidence: float = 0.82,
    output_sort: str = "citations",
    use_fastpath: bool = True,
    force_browser: bool = False,
) -> None:
    """
    Hybrid Scholar Extractor:
    1. Tries the ultra-fast protocol HTTP client first (cstart=0&pagesize=100) in ~1 second.
    2. Seamlessly falls back to human-emulating Playwright Chromium browser if CAPTCHA or blocks are met.
    """
    user_id = extract_scholar_user_id(profile_url)
    extracted_data = []
    scholar_citations = "N/A"
    scholar_h_index = "N/A"
    fastpath_succeeded = False

    # ==========================================
    # Fast-Path Protocol Extraction (HTTP)
    # ==========================================
    if use_fastpath and not force_browser and user_id:
        logger.info(f"[Fast-Path] Attempting direct HTTP protocol fetch for scholar: {user_id}...")
        http_client = ScholarHttpClient()
        max_recs = (max_clicks + 1) * 20 if max_clicks > 0 else 0
        profile, is_blocked = http_client.fetch_all_profile_records_fast(
            user_id, max_records=max_recs, sort_by=output_sort
        )
        if profile and not is_blocked and profile.publications:
            logger.info(f"[Fast-Path] Succeeded! Extracted {len(profile.publications)} records via HTTP protocol.")
            scholar_citations = profile.total_citations
            scholar_h_index = profile.h_index

            # Build extracted_data dictionary with all required schema fields
            for pub in profile.publications:
                extracted_data.append({
                    "Title": pub.get("Title", "N/A"),
                    "Authors": pub.get("Authors", "N/A"),
                    "Journal/Venue": pub.get("Journal/Venue", "N/A"),
                    "Citations": pub.get("Citations", 0),
                    "WoS Citations": "N/A",
                    "Year": pub.get("Year", "N/A"),
                    "Publication Date": pub.get("Year", "N/A"),
                    "Journal": "N/A",
                    "Conference": "N/A",
                    "Volume": "N/A",
                    "Issue": "N/A",
                    "Pages": "N/A",
                    "Publisher": "N/A",
                    "Description": "N/A",
                    "DOI": "N/A",
                    "DOI Source": "N/A",
                    "DOI Confidence": "none",
                    "DOI Evidence JSON": "{}",
                    "OpenAlex ID": "N/A",
                    "OpenAlex DOI": "N/A",
                    "OpenAlex Match Confidence": "none",
                    "OpenAlex Match Method": "N/A",
                    "OpenAlex Authors": "N/A",
                    "OpenAlex Author Count": "N/A",
                    "OpenAlex Corresponding Authors": "N/A",
                    "OpenAlex Corresponding Author Positions": "N/A",
                    "OpenAlex Source": "N/A",
                    "OpenAlex Publisher": "N/A",
                    "OpenAlex Volume": "N/A",
                    "OpenAlex Issue": "N/A",
                    "OpenAlex Pages": "N/A",
                    "OpenAlex Evidence JSON": "{}",
                    "Metadata Enrichment Source": "N/A",
                    "Metadata Enrichment Confidence": "none",
                    "Scholar Detail Fields JSON": "{}",
                    "Target Author Query": "N/A",
                    "Target Author Position": "N/A",
                    "Target Author Matched Name": "N/A",
                    "Highlighted Authors": pub.get("Authors", "N/A"),
                    "Corresponding Author Query": "N/A",
                    "Corresponding Author Position": "N/A",
                    "Corresponding Author Matched Name": "N/A",
                    "Is Target Author Corresponding": "N/A",
                    "Highlighted Corresponding Authors": pub.get("Authors", "N/A"),
                    "Corresponding Evidence Source": "N/A",
                    "Corresponding Confidence": "none",
                    "Corresponding Evidence JSON": "{}",
                    "Scholar Author Citations": scholar_citations,
                    "Scholar Author H-Index": scholar_h_index,
                    "WoS Author Citations": "N/A",
                    "WoS Author Citations (Non-Self)": "N/A",
                    "WoS Author H-Index": "N/A",
                    "Scholar Article ID": pub.get("Scholar Article ID", ""),
                })

            # Fast Refinement: direct view_citation HTTP fetching without opening browser modals
            refine_indices = []
            if refine_mode == "auto":
                for idx, data in enumerate(extracted_data):
                    if fetch_doi or "..." in data["Authors"]:
                        refine_indices.append(idx)
            elif refine_mode == "all":
                refine_indices = list(range(len(extracted_data)))
            elif refine_mode != "none":
                try:
                    parts = [int(p.strip()) - 1 for p in refine_mode.split(",") if p.strip().isdigit()]
                    refine_indices = [p for p in parts if 0 <= p < len(extracted_data)]
                except Exception:
                    pass

            to_refine = refine_indices[:refine_limit]
            if to_refine:
                logger.info(f"[Fast-Path] Refining {len(to_refine)} papers via direct view_citation endpoint...")
                for idx in to_refine:
                    art_id = extracted_data[idx].get("Scholar Article ID")
                    if art_id:
                        fields = http_client.fetch_citation_details_fast(user_id, art_id)
                        if fields:
                            extracted_data[idx]["Scholar Detail Fields JSON"] = json.dumps(fields, ensure_ascii=False)
                            doi_ev = extract_doi_from_scholar_details(fields)
                            if doi_ev.get("doi") and doi_ev["doi"] != "N/A":
                                extracted_data[idx]["DOI"] = doi_ev["doi"]
                                extracted_data[idx]["DOI Source"] = doi_ev["source"]
                                extracted_data[idx]["DOI Confidence"] = doi_ev["confidence"]
                                extracted_data[idx]["DOI Evidence JSON"] = json.dumps(doi_ev.get("evidence", {}), ensure_ascii=False)
                            for f_name, f_val in fields.items():
                                k_low = f_name.lower()
                                if "journal" in k_low:
                                    extracted_data[idx]["Journal"] = f_val
                                    set_if_missing(extracted_data[idx], "Journal/Venue", f_val)
                                elif "volume" in k_low:
                                    extracted_data[idx]["Volume"] = f_val
                                elif "issue" in k_low or "number" in k_low:
                                    extracted_data[idx]["Issue"] = f_val
                                elif "pages" in k_low:
                                    extracted_data[idx]["Pages"] = f_val
                                elif "publisher" in k_low:
                                    extracted_data[idx]["Publisher"] = f_val
                                elif "description" in k_low:
                                    extracted_data[idx]["Description"] = f_val
                                elif "authors" in k_low and "..." in extracted_data[idx].get("Authors", ""):
                                    extracted_data[idx]["Authors"] = f_val

            fastpath_succeeded = True

            # If Web of Science was requested, launch lightweight browser only for WoS
            if wos_id:
                logger.info("Initializing Web of Science extraction for Fast-Path results...")
                async with async_playwright() as p:
                    user_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".playwright_profile"))
                    context = await p.chromium.launch_persistent_context(
                        user_data_dir, headless=False, viewport={"width": 1280, "height": 800}
                    )
                    page = context.pages[0] if context.pages else await context.new_page()
                    try:
                        wos_res = await scrape_wos_citations(wos_id, page, fetch_wos_ut=fetch_wos_ut)
                        wos_citations_map = wos_res.get("citations_map", {})
                        wos_sum_cited = wos_res.get("sum_cited", "N/A")
                        wos_sum_cited_without_self = wos_res.get("sum_cited_without_self", "N/A")
                        wos_h_index = wos_res.get("h_index", "N/A")
                        for idx, data in enumerate(extracted_data):
                            title = data["Title"]
                            norm_title = re.sub(r'[^a-z0-9]', '', title.lower())
                            wos_info = wos_citations_map.get(norm_title, {"citations": "N/A", "accession_number": "N/A"})
                            extracted_data[idx]["WoS Citations"] = wos_info.get("citations", "N/A")
                            extracted_data[idx]["WoS Author Citations"] = wos_sum_cited
                            extracted_data[idx]["WoS Author Citations (Non-Self)"] = wos_sum_cited_without_self
                            extracted_data[idx]["WoS Author H-Index"] = wos_h_index
                            if fetch_wos_ut:
                                extracted_data[idx]["WoS Accession Number"] = wos_info.get("accession_number", "N/A")
                    finally:
                        await context.close()
        else:
            logger.warning("[Fast-Path] Encountered CAPTCHA/block or zero records. Falling back to Playwright browser automation...")

    # ==========================================
    # Slow-Track Playwright Browser Flow (Fallback / Forced)
    # ==========================================
    if not fastpath_succeeded:
        logger.info("Initializing Playwright Async Engine (Browser Track)...")
        async with async_playwright() as p:
            # Define a persistent user data directory inside the workspace
            user_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".playwright_profile"))
            remind_first_run_login_setup(user_data_dir, uses_wos=bool(wos_id))
            logger.info(f"Launching visible Chromium with persistent profile: {user_data_dir}...")
            
            context = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--start-maximized"]
            )
            
            # Get already opened page or open a new one
            pages = context.pages
            page = pages[0] if pages else await context.new_page()
            
            logger.info(f"Navigating to Scholar Profile: {profile_url}...")
            try:
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"Initial navigation warning (timeout/other): {e}. Proceeding anyway...")
            
            # Check for CAPTCHA immediately upon loading
            await handle_captcha_if_needed(page)
            
            # Click reject cookies if the consent dialog appears to clean the viewport
            try:
                reject_cookies = page.locator("button:has-text('Reject Unnecessary Cookies')")
                if await reject_cookies.is_visible():
                    await reject_cookies.click()
                    logger.info("Cookie consent dialog dismissed.")
            except Exception:
                pass
                
            show_more_selector = "#gsc_bpf_more"
            
            # Dynamic Pagination Loop ("Show more")
            click_count = 0
            while True:
                if click_count >= max_clicks:
                    logger.info(f"Reached maximum of {max_clicks} 'Show more' clicks; stopping pagination.")
                    break

                await handle_captcha_if_needed(page)
                show_more_button = page.locator(show_more_selector)

                if await show_more_button.count() == 0 or await show_more_button.get_attribute("disabled") is not None:
                    logger.info("Show more button is no longer active. Reached the end of the profile.")
                    break

                raw_delay = random.gauss(4.5, 1.2)
                delay = max(2.0, min(8.0, raw_delay))
                logger.info(f"Human-like pacing delay: waiting {delay:.2f}s before click #{click_count + 1}.")
                await asyncio.sleep(delay)

                initial_row_count = await page.locator("tr.gsc_a_tr").count()
                await show_more_button.scroll_into_view_if_needed()

                bbox = await show_more_button.bounding_box()
                if bbox is None:
                    await show_more_button.click(timeout=10000)
                else:
                    margin_x = bbox["width"] * 0.05
                    margin_y = bbox["height"] * 0.05
                    click_x = bbox["x"] + random.uniform(margin_x, bbox["width"] - margin_x)
                    click_y = bbox["y"] + random.uniform(margin_y, bbox["height"] - margin_y)
                    await page.mouse.move(click_x, click_y, steps=30)
                    await page.mouse.click(click_x, click_y)

                click_count += 1
                if click_count >= max_clicks:
                    break

                rows_loaded = False
                for _ in range(25):
                    await asyncio.sleep(0.2)
                    await handle_captcha_if_needed(page)
                    new_row_count = await page.locator("tr.gsc_a_tr").count()
                    if new_row_count > initial_row_count:
                        rows_loaded = True
                        break

                if not rows_loaded and (await show_more_button.count() == 0 or await show_more_button.get_attribute("disabled") is not None):
                    break

            logger.info("All publications expanded. Beginning data extraction...")
            try:
                rows_stats = await page.locator("tr:has(.gsc_rsb_f)").all()
                for r in rows_stats:
                    label_el = r.locator(".gsc_rsb_f")
                    val_els = r.locator("td.gsc_rsb_std")
                    if await label_el.count() > 0 and await val_els.count() > 0:
                        label = (await label_el.nth(0).inner_text()).strip().lower()
                        val_all = (await val_els.nth(0).inner_text()).strip()
                        if "citations" in label:
                            scholar_citations = val_all
                        elif "h-index" in label:
                            scholar_h_index = val_all
            except Exception as e:
                logger.warning(f"Failed to extract Google Scholar author stats: {e}")

            rows = await page.locator("tr.gsc_a_tr").all()
            logger.info(f"Total publication rows identified: {len(rows)}")

            for idx, row in enumerate(rows, 1):
                title = "N/A"
                authors = "N/A"
                venue = "N/A"
                citations = 0
                year = "N/A"
                try:
                    title_loc = row.locator(".gsc_a_at")
                    if await title_loc.count() > 0:
                        title = (await title_loc.inner_text()).strip()
                    gray_locs = row.locator(".gsc_a_t .gs_gray")
                    if await gray_locs.count() > 0:
                        authors = (await gray_locs.nth(0).inner_text()).strip()
                    if await gray_locs.count() > 1:
                        venue = (await gray_locs.nth(1).inner_text()).strip()
                    citations_loc = row.locator(".gsc_a_c a")
                    if await citations_loc.count() > 0:
                        cit_text = (await citations_loc.inner_text()).strip()
                        if cit_text:
                            clean_cit = re.sub(r'\D', '', cit_text)
                            citations = int(clean_cit) if clean_cit else 0
                    year_loc = row.locator(".gsc_a_y span")
                    if await year_loc.count() > 0:
                        year = (await year_loc.inner_text()).strip()
                    else:
                        year_loc_direct = row.locator(".gsc_a_y")
                        if await year_loc_direct.count() > 0:
                            year = (await year_loc_direct.inner_text()).strip()
                except Exception as e:
                    logger.error(f"Row {idx}: Failed to extract columns cleanly: {e}")

                extracted_data.append({
                    "Title": title,
                    "Authors": authors,
                    "Journal/Venue": venue,
                    "Citations": citations,
                    "WoS Citations": "N/A",
                    "Year": year,
                    "Publication Date": year,
                    "Journal": "N/A",
                    "Conference": "N/A",
                    "Volume": "N/A",
                    "Issue": "N/A",
                    "Pages": "N/A",
                    "Publisher": "N/A",
                    "Description": "N/A",
                    "DOI": "N/A",
                    "DOI Source": "N/A",
                    "DOI Confidence": "none",
                    "DOI Evidence JSON": "{}",
                    "OpenAlex ID": "N/A",
                    "OpenAlex DOI": "N/A",
                    "OpenAlex Match Confidence": "none",
                    "OpenAlex Match Method": "N/A",
                    "OpenAlex Authors": "N/A",
                    "OpenAlex Author Count": "N/A",
                    "OpenAlex Corresponding Authors": "N/A",
                    "OpenAlex Corresponding Author Positions": "N/A",
                    "OpenAlex Source": "N/A",
                    "OpenAlex Publisher": "N/A",
                    "OpenAlex Volume": "N/A",
                    "OpenAlex Issue": "N/A",
                    "OpenAlex Pages": "N/A",
                    "OpenAlex Evidence JSON": "{}",
                    "Metadata Enrichment Source": "N/A",
                    "Metadata Enrichment Confidence": "none",
                    "Scholar Detail Fields JSON": "{}",
                    "Target Author Query": "N/A",
                    "Target Author Position": "N/A",
                    "Target Author Matched Name": "N/A",
                    "Highlighted Authors": authors,
                    "Corresponding Author Query": "N/A",
                    "Corresponding Author Position": "N/A",
                    "Corresponding Author Matched Name": "N/A",
                    "Is Target Author Corresponding": "N/A",
                    "Highlighted Corresponding Authors": authors,
                    "Corresponding Evidence Source": "N/A",
                    "Corresponding Confidence": "none",
                    "Corresponding Evidence JSON": "{}",
                    "Scholar Author Citations": scholar_citations,
                    "Scholar Author H-Index": scholar_h_index,
                    "WoS Author Citations": "N/A",
                    "WoS Author Citations (Non-Self)": "N/A",
                    "WoS Author H-Index": "N/A"
                })

            # Secondary modal refinement in Playwright
            refine_indices = []
            if refine_mode == "auto":
                for idx, data in enumerate(extracted_data):
                    if fetch_doi or "..." in data["Authors"]:
                        refine_indices.append(idx)
            elif refine_mode == "all":
                refine_indices = list(range(len(extracted_data)))
            elif refine_mode != "none":
                try:
                    parts = [int(p.strip()) - 1 for p in refine_mode.split(",") if p.strip().isdigit()]
                    refine_indices = [p for p in parts if 0 <= p < len(extracted_data)]
                except Exception as e:
                    logger.error(f"Failed to parse refine indices '{refine_mode}': {e}")

            if refine_indices:
                to_refine = refine_indices[:refine_limit]
                logger.info(f"Refining top {len(to_refine)} selected papers in browser...")
                for idx in to_refine:
                    try:
                        await handle_captcha_if_needed(page)
                        title_locator = page.locator("tr.gsc_a_tr a.gsc_a_at").nth(idx)
                        if await title_locator.count() == 0:
                            continue
                        await title_locator.scroll_into_view_if_needed()
                        await asyncio.sleep(random.uniform(1.5, 3.5))
                        await title_locator.click(timeout=10000)
                        await page.wait_for_selector("#gsc_oci_table", timeout=12000)
                        await handle_captcha_if_needed(page)

                        fields = await page.locator(".gsc_oci_field").all_inner_texts()
                        values = await page.locator(".gsc_oci_value").all_inner_texts()
                        detail_fields = {f.strip(): v.strip() for f, v in zip(fields, values) if f.strip() and v.strip()}
                        extracted_data[idx]["Scholar Detail Fields JSON"] = json.dumps(detail_fields, ensure_ascii=False)

                        doi_ev = extract_doi_from_scholar_details(detail_fields)
                        if doi_ev.get("doi") and doi_ev["doi"] != "N/A":
                            extracted_data[idx]["DOI"] = doi_ev["doi"]
                            extracted_data[idx]["DOI Source"] = doi_ev["source"]
                            extracted_data[idx]["DOI Confidence"] = doi_ev["confidence"]
                            extracted_data[idx]["DOI Evidence JSON"] = json.dumps(doi_ev.get("evidence", {}), ensure_ascii=False)

                        back_btn = page.locator("#gs_hdr_bck, #gsc_oci_back, a.gs_ico_back")
                        if await back_btn.count() > 0 and await back_btn.is_visible():
                            await back_btn.click()
                            await page.wait_for_selector("#gsc_prf", timeout=10000)
                    except Exception as e:
                        logger.error(f"Failed to refine paper #{idx + 1}: {e}")

            # WoS extraction
            if wos_id:
                try:
                    wos_res = await scrape_wos_citations(wos_id, page, fetch_wos_ut=fetch_wos_ut)
                    wos_citations_map = wos_res.get("citations_map", {})
                    for idx, data in enumerate(extracted_data):
                        title = data["Title"]
                        norm_title = re.sub(r'[^a-z0-9]', '', title.lower())
                        wos_info = wos_citations_map.get(norm_title, {"citations": "N/A", "accession_number": "N/A"})
                        extracted_data[idx]["WoS Citations"] = wos_info.get("citations", "N/A")
                        extracted_data[idx]["WoS Author Citations"] = wos_res.get("sum_cited", "N/A")
                        extracted_data[idx]["WoS Author Citations (Non-Self)"] = wos_res.get("sum_cited_without_self", "N/A")
                        extracted_data[idx]["WoS Author H-Index"] = wos_res.get("h_index", "N/A")
                        if fetch_wos_ut:
                            extracted_data[idx]["WoS Accession Number"] = wos_info.get("accession_number", "N/A")
                except Exception as e:
                    logger.error(f"Error matching Web of Science citations: {e}")

            await context.close()

        if openalex_enrich and extracted_data:
            logger.info("Enriching records via OpenAlex before Crossref fallback...")
            enrich_records_with_openalex_batch(
                extracted_data,
                api_key=openalex_api_key,
                min_confidence=openalex_min_confidence,
                max_records=openalex_max_records,
            )

        # ==========================================
        # Fetching DOIs via Crossref fallback
        # ==========================================
        if fetch_doi and extracted_data:
            logger.info("Resolving missing DOIs via Crossref after Google Scholar detail extraction...")
            import time
            try:
                for idx, data in enumerate(extracted_data):
                    if clean_bib_value(data.get("DOI")):
                        logger.info(f"[{idx+1}/{len(extracted_data)}] DOI already available from {data.get('DOI Source', 'existing source')}; skipping Crossref.")
                        continue
                    title = data["Title"]
                    logger.info(f"[{idx+1}/{len(extracted_data)}] Querying Crossref DOI for: '{title[:50]}...'")
                    doi_evidence = fetch_doi_evidence_via_crossref(title)
                    extracted_data[idx]["DOI"] = doi_evidence.get("doi", "N/A")
                    extracted_data[idx]["DOI Source"] = doi_evidence.get("source", "Crossref")
                    extracted_data[idx]["DOI Confidence"] = doi_evidence.get("confidence", "none")
                    extracted_data[idx]["DOI Evidence JSON"] = json.dumps(doi_evidence.get("evidence", {}), ensure_ascii=False)
                    # Polite rate-limiting delay for Crossref API
                    time.sleep(0.3)
            except Exception as e:
                logger.error(f"Crossref DOI fetching failed/interrupted: {e}")
                print("\n" + "="*70)
                print("⚠️  [警告] Crossref DOI 查询 (方案二) 失败或被限制。")
                print("建议采用【方案一】：")
                print("使用 orcid_extractor.py 脚本拉取该学者的 ORCID 记录。")
                print("ORCID 记录包含完美的、官方认证的原始 DOI 链接！")
                print("命令示例: python orcid_extractor.py --orcid [学者ORCID]")
                print("="*70)
        
        for record in extracted_data:
            annotate_target_author(record, target_author, target_author_position, author_highlight)
            annotate_corresponding_author(record, corresponding_author, corresponding_author_position, author_highlight, fetch_corresponding)

        # ==========================================
        # Sorting and Saving CSV & Stats Summary
        # ==========================================
        if extracted_data:
            df = pd.DataFrame(extracted_data)
            
            df_sorted = sort_output_dataframe(df, output_sort)
            
            # Save to CSV (using utf-8-sig for perfect Windows Excel encoding)
            df_sorted.to_csv(output_csv, index=False, encoding="utf-8-sig")
            logger.info(f"Scraped data successfully saved to: {os.path.abspath(output_csv)}")
            logger.info(f"Total records saved: {len(df_sorted)}")

            write_citation_exports(df_sorted.to_dict("records"), output_csv, citation_format, author_highlight)
            
            # Extract stats metrics for JSON & terminal card
            first_row = extracted_data[0]
            wos_sum_cited_val = first_row.get("WoS Author Citations", "N/A")
            wos_sum_cited_without_self_val = first_row.get("WoS Author Citations (Non-Self)", "N/A")
            wos_h_index_val = first_row.get("WoS Author H-Index", "N/A")
            
            stats_summary = {
                "Google Scholar": {
                    "Total Citations": scholar_citations,
                    "H-Index": scholar_h_index
                },
                "Web of Science": {
                    "Total Citations": wos_sum_cited_val,
                    "Total Citations (Without Self-Citations)": wos_sum_cited_without_self_val,
                    "H-Index": wos_h_index_val
                }
            }
            
            # Save stats companion JSON file
            base_path, _ = os.path.splitext(output_csv)
            stats_json_path = f"{base_path}_stats.json"
            try:
                with open(stats_json_path, "w", encoding="utf-8") as f:
                    json.dump(stats_summary, f, indent=4, ensure_ascii=False)
                logger.info(f"Stats summary successfully saved to: {os.path.abspath(stats_json_path)}")
            except Exception as je:
                logger.warning(f"Failed to save companion stats JSON: {je}")
                
            # Print beautiful Author Impact Metrics Card
            print("\n" + "="*60)
            print("📊  【学者影响力指标汇总 / AUTHOR IMPACT METRICS SUMMARY】")
            print("="*60)
            print(f"  Google Scholar:")
            print(f"    - 被引总数 (Total Citations): {scholar_citations}")
            print(f"    - H-Index:                   {scholar_h_index}")
            if wos_id:
                print(f"  Web of Science (ID: {wos_id}):")
                print(f"    - 被引总数 (Total Citations): {wos_sum_cited_val}")
                print(f"    - 他引总数 (Non-Self Citations): {wos_sum_cited_without_self_val}")
                print(f"    - H-Index:                   {wos_h_index_val}")
            else:
                print(f"  Web of Science:")
                print(f"    - 被引总数 (Total Citations): N/A (未提供 --wos-id)")
                print(f"    - 他引总数 (Non-Self Citations): N/A (未提供 --wos-id)")
                print(f"    - H-Index:                   {wos_h_index_val}")
            print("="*60 + "\n")
        else:
            logger.warning("No records extracted. CSV was not generated.")

def main():
    parser = argparse.ArgumentParser(
        description="Scrape Google Scholar profiles securely using Playwright with CAPTCHA self-healing wait."
    )
    parser.add_argument(
        "--user-id",
        default="SQdUxqYAAAAJ",
        help="Google Scholar user profile ID (default: SQdUxqYAAAAJ)."
    )
    parser.add_argument(
        "--output",
        default="google_scholar_scraped.csv",
        help="Output CSV filepath (default: google_scholar_scraped.csv)."
    )
    parser.add_argument(
        "--max-clicks",
        type=int,
        default=5,
        help="Maximum number of 'Show more' clicks to perform (default 5) to reduce data load."
    )
    parser.add_argument(
        "--refine",
        default="none",
        help="Secondary refinement mode: 'auto' (truncations), 'none', 'all', or comma-separated indices (e.g. '1,2,5')."
    )
    parser.add_argument(
        "--refine-limit",
        type=int,
        default=10,
        help="Maximum number of papers to refine (default 10) to avoid bot detection."
    )
    parser.add_argument(
        "--fetch-doi",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Resolve DOI links by default using Scholar detail, OpenAlex, then Crossref fallback. Use --no-fetch-doi for a faster minimal run."
    )
    parser.add_argument(
        "--wos-id",
        default=None,
        help="Web of Science ResearcherID or ORCID iD for citation mapping (e.g., 0000-0002-0499-6138)."
    )
    parser.add_argument(
        "--fetch-wos-ut",
        dest="fetch_wos_ut",
        action="store_true",
        help="Explicitly enable extraction of Web of Science Accession Numbers (UT)."
    )
    parser.add_argument(
        "--no-wos-ut",
        dest="fetch_wos_ut",
        action="store_false",
        help="Explicitly disable extraction of Web of Science Accession Numbers (UT)."
    )
    parser.add_argument(
        "--citation-format",
        default="ask",
        help="Optional reference export format: ask, none, apa, mla, chicago, harvard, latex/bibtex, ama, gbt/gbt7714, gbt2025/gbt7714-2025, all, or comma-separated values."
    )
    parser.add_argument(
        "--output-sort",
        choices=["citations", "publication-date", "year", "none"],
        default="citations",
        help="CSV and reference export sort order. Default is citations; use publication-date for newest publications first."
    )
    parser.add_argument(
        "--target-author",
        default="",
        help="Author name to locate in each publication's author list. Adds target author position columns and enables author highlighting in reference exports."
    )
    parser.add_argument(
        "--target-author-position",
        type=int,
        default=0,
        help="1-based author position to mark when the target author name is ambiguous or unavailable."
    )
    parser.add_argument(
        "--author-highlight",
        choices=["none", "bold", "underline", "both"],
        default="bold",
        help="Highlight style for the target author in reference exports and the Highlighted Authors CSV column."
    )
    parser.add_argument(
        "--corresponding-author",
        default="",
        help="Manually specified corresponding author name. Manual values take priority over automatic metadata lookup."
    )
    parser.add_argument(
        "--corresponding-author-position",
        type=int,
        default=0,
        help="1-based manually specified corresponding author position."
    )
    parser.add_argument(
        "--fetch-corresponding",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Infer corresponding authors by default, reusing OpenAlex enrichment first. Use --no-fetch-corresponding to disable."
    )
    parser.add_argument(
        "--openalex-enrich",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use OpenAlex by default to enrich DOI, complete authors, corresponding authors, source, publisher, volume, issue, and pages. Use --no-openalex-enrich for offline/minimal runs."
    )
    parser.add_argument(
        "--openalex-api-key",
        default=os.getenv("OPENALEX_API_KEY", ""),
        help="OpenAlex API key. Defaults to OPENALEX_API_KEY when set."
    )
    parser.add_argument(
        "--openalex-max-records",
        type=int,
        default=0,
        help="Maximum records to enrich through OpenAlex; 0 means all records."
    )
    parser.add_argument(
        "--openalex-min-confidence",
        type=float,
        default=0.82,
        help="Minimum OpenAlex title-match confidence required to overwrite missing metadata for non-DOI matches."
    )
    parser.add_argument(
        "--fast",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use ultra-fast HTTP protocol path (default: True). Automatically falls back to Playwright browser if blocked."
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Force using Playwright Chromium browser automation instead of Fast-Path HTTP protocol."
    )
    parser.set_defaults(fetch_wos_ut=None)
    
    args = parser.parse_args()
    
    fetch_wos_ut = args.fetch_wos_ut
    if args.wos_id and fetch_wos_ut is None:
        print("\n" + "="*80)
        print("📋  [提示 / PROMPT]")
        print("是否需要为每篇论文提取 Web of Science 入藏号 (Accession Number, UT)？")
        print("Do you want to extract and include Web of Science Accession Numbers (UT) in the CSV?")
        print("="*80)
        try:
            choice = input("请输入 Y (需要) 或 N (不需要)，默认 [N]: ").strip().lower()
            fetch_wos_ut = choice == 'y'
        except Exception:
            fetch_wos_ut = False
            
    if args.refine == "none" and (args.fetch_doi or args.openalex_enrich):
        args.refine = "auto"

    # Standard profile URL format
    profile_url = f"https://scholar.google.com/citations?hl=en&user={args.user_id.strip()}"
    
    # Run Async scraping loop
    try:
        asyncio.run(scrape_scholar_profile(
            profile_url, 
            args.output, 
            args.max_clicks, 
            args.refine, 
            args.refine_limit, 
            args.fetch_doi,
            wos_id=args.wos_id,
            fetch_wos_ut=fetch_wos_ut,
            citation_format=args.citation_format,
            target_author=args.target_author,
            target_author_position=args.target_author_position,
            author_highlight=args.author_highlight,
            corresponding_author=args.corresponding_author,
            corresponding_author_position=args.corresponding_author_position,
            fetch_corresponding=args.fetch_corresponding,
            openalex_enrich=args.openalex_enrich,
            openalex_api_key=args.openalex_api_key,
            openalex_max_records=args.openalex_max_records,
            openalex_min_confidence=args.openalex_min_confidence,
            output_sort=args.output_sort,
            use_fastpath=args.fast,
            force_browser=args.browser,
        ))
    except KeyboardInterrupt:
        logger.info("Process interrupted by user. Exiting.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Google Scholar Playwright extraction failed: {e}")
        print("\n" + "="*70)
        print("⚠️  [警告] Google Scholar Playwright (防封锁人类模拟) 抓取失败或被中断。")
        print("您可以选择运行以下备用方法：")
        print("1. 使用 scholarly 开源库 (简单 API 封装，不使用浏览器，但极易被谷歌封锁)")
        print("2. 使用 免费代理 / 代理 API 方式 (需配置代理服务器)")
        print("="*70)
        choice = input("请输入您想尝试的备份方法编号 (1/2)，或按回车退出: ").strip()
        if choice == "1":
            print("\n正在尝试运行 scholarly 备份方案...")
            try:
                from scholarly import scholarly
                print(f"Searching author ID: {args.user_id}...")
                author = scholarly.search_author_id(args.user_id)
                print("Filling publications list...")
                author = scholarly.fill(author, sections=['publications'])
                publications = author.get('publications', [])
                logger.info(f"Found {len(publications)} publications via scholarly.")
                if publications:
                    # Extract H-Index and total citations from scholarly profile
                    scholar_citations = author.get('citedby', 'N/A')
                    scholar_h_index = author.get('hindex', 'N/A')
                    
                    # Save to CSV
                    import pandas as pd
                    extracted = []
                    for pub in publications:
                        bib = pub.get('bib', {})
                        bib_doi = format_doi_url(bib.get('doi', bib.get('DOI', '')))
                        bib_doi_found = bib_doi != "N/A"
                        extracted.append({
                            "Title": bib.get('title', 'N/A'),
                            "Authors": bib.get('author', 'N/A'),
                            "Journal/Venue": bib.get('journal', bib.get('venue', 'N/A')),
                            "Citations": pub.get('num_citations', 0),
                            "WoS Citations": "N/A",
                            "Year": bib.get('pub_year', 'N/A'),
                            "Publication Date": bib.get('pub_year', 'N/A'),
                            "Journal": bib.get('journal', 'N/A'),
                            "Conference": bib.get('conference', bib.get('venue', 'N/A')),
                            "Volume": bib.get('volume', 'N/A'),
                            "Issue": bib.get('number', bib.get('issue', 'N/A')),
                            "Pages": bib.get('pages', 'N/A'),
                            "Publisher": bib.get('publisher', 'N/A'),
                            "Description": bib.get('abstract', 'N/A'),
                            "DOI": bib_doi,
                            "DOI Source": "scholarly bib" if bib_doi_found else "N/A",
                            "DOI Confidence": "medium" if bib_doi_found else "none",
                            "DOI Evidence JSON": json.dumps({"bib_doi": bib.get('doi', bib.get('DOI', ''))}, ensure_ascii=False) if bib_doi_found else "{}",
                            "OpenAlex ID": "N/A",
                            "OpenAlex DOI": "N/A",
                            "OpenAlex Match Confidence": "none",
                            "OpenAlex Match Method": "N/A",
                            "OpenAlex Authors": "N/A",
                            "OpenAlex Author Count": "N/A",
                            "OpenAlex Corresponding Authors": "N/A",
                            "OpenAlex Corresponding Author Positions": "N/A",
                            "OpenAlex Source": "N/A",
                            "OpenAlex Publisher": "N/A",
                            "OpenAlex Volume": "N/A",
                            "OpenAlex Issue": "N/A",
                            "OpenAlex Pages": "N/A",
                            "OpenAlex Evidence JSON": "{}",
                            "Metadata Enrichment Source": "N/A",
                            "Metadata Enrichment Confidence": "none",
                            "Scholar Detail Fields JSON": json.dumps(bib, ensure_ascii=False),
                            "Target Author Query": "N/A",
                            "Target Author Position": "N/A",
                            "Target Author Matched Name": "N/A",
                            "Highlighted Authors": bib.get('author', 'N/A'),
                            "Corresponding Author Query": "N/A",
                            "Corresponding Author Position": "N/A",
                            "Corresponding Author Matched Name": "N/A",
                            "Is Target Author Corresponding": "N/A",
                            "Highlighted Corresponding Authors": bib.get('author', 'N/A'),
                            "Corresponding Evidence Source": "N/A",
                            "Corresponding Confidence": "none",
                            "Corresponding Evidence JSON": "{}",
                            "Scholar Author Citations": scholar_citations,
                            "Scholar Author H-Index": scholar_h_index,
                            "WoS Author Citations": "N/A",
                            "WoS Author Citations (Non-Self)": "N/A",
                            "WoS Author H-Index": "N/A"
                        })
                    if args.openalex_enrich and extracted:
                        import time
                        limit = args.openalex_max_records if args.openalex_max_records and args.openalex_max_records > 0 else len(extracted)
                        for idx, record in enumerate(extracted[:limit]):
                            logger.info(f"[fallback {idx+1}/{min(limit, len(extracted))}] Querying OpenAlex for: '{record.get('Title', '')[:50]}...'")
                            enrich_record_with_openalex(record, args.openalex_api_key, args.openalex_min_confidence)
                            time.sleep(0.12 if args.openalex_api_key else 0.35)
                    for record in extracted:
                        annotate_target_author(record, args.target_author, args.target_author_position, args.author_highlight)
                        annotate_corresponding_author(record, args.corresponding_author, args.corresponding_author_position, args.author_highlight, args.fetch_corresponding)
                    df = pd.DataFrame(extracted)
                    df_sorted = sort_output_dataframe(df, args.output_sort)
                    df_sorted.to_csv(args.output, index=False, encoding="utf-8-sig")
                    logger.info(f"Successfully saved scholarly fallback data to: {args.output}")
                    write_citation_exports(df_sorted.to_dict("records"), args.output, args.citation_format, args.author_highlight)
                    
                    # Save stats summary companion JSON
                    stats_summary = {
                        "Google Scholar": {
                            "Total Citations": scholar_citations,
                            "H-Index": scholar_h_index
                        },
                        "Web of Science": {
                            "Total Citations": "N/A",
                            "Total Citations (Without Self-Citations)": "N/A",
                            "H-Index": "N/A"
                        }
                    }
                    base_path, _ = os.path.splitext(args.output)
                    stats_json_path = f"{base_path}_stats.json"
                    try:
                        with open(stats_json_path, "w", encoding="utf-8") as f:
                            json.dump(stats_summary, f, indent=4, ensure_ascii=False)
                    except Exception:
                        pass
                        
                    # Print metrics card for fallback
                    print("\n" + "="*60)
                    print("📊  【学者影响力指标汇总 / AUTHOR IMPACT METRICS SUMMARY】")
                    print("="*60)
                    print(f"  Google Scholar (via scholarly fallback):")
                    print(f"    - 被引总数 (Total Citations): {scholar_citations}")
                    print(f"    - H-Index:                   {scholar_h_index}")
                    print(f"  Web of Science:")
                    print(f"    - 被引总数 (Total Citations): N/A")
                    print(f"    - 他引总数 (Non-Self Citations): N/A")
                    print(f"    - H-Index:                   N/A")
                    print("="*60 + "\n")
                else:
                    logger.error("scholarly found no publications.")
                    sys.exit(1)
            except Exception as se:
                logger.critical(f"scholarly fallback also failed: {se}")
                sys.exit(1)
        elif choice == "2":
            print("\n提示：代理旋转方法需要配置海外代理服务端口或购买 ScraperAPI 等服务，请检查您的 .env 代理配置后再试。")
            sys.exit(1)
        else:
            print("退出。")
            sys.exit(1)

if __name__ == "__main__":
    main()

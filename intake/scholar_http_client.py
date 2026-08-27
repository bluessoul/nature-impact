# -*- coding: utf-8 -*-
"""
Fast-Path Protocol Client for Google Scholar.
Fetches scholar citation profiles and individual paper metadata directly via HTTP AJAX endpoints
without spinning up a heavy browser instance. Automatically falls back to Playwright if CAPTCHA is detected.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_SCHOLAR_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

SCHOLAR_BASE_URL = "https://scholar.google.com/citations"


@dataclass
class ScholarAuthorProfile:
    user_id: str
    name: str = ""
    affiliation: str = ""
    interests: List[str] = field(default_factory=list)
    total_citations: str = "N/A"
    citations_since_recent: str = "N/A"
    h_index: str = "N/A"
    h_index_since_recent: str = "N/A"
    i10_index: str = "N/A"
    i10_index_since_recent: str = "N/A"
    publications: List[Dict[str, Any]] = field(default_factory=list)
    raw_stats: Dict[str, Any] = field(default_factory=dict)
    source: str = "http_fastpath"


def extract_scholar_user_id(query_or_url: str) -> str:
    """Extracts Scholar User ID from a URL or raw ID string."""
    if not query_or_url:
        return ""
    text = str(query_or_url).strip()
    match = re.search(r"[?&]user=([a-zA-Z0-9_-]{12})", text)
    if match:
        return match.group(1)
    # Direct 12-char alphanumeric ID check
    if re.match(r"^[a-zA-Z0-9_-]{12}$", text):
        return text
    return text


def detect_local_browser_cookie_header() -> str:
    """
    Attempts to read valid google.com cookies from local Chrome / Edge / Playwright profile.
    Returns standard 'Cookie: key=val; ...' string or empty string if not found.
    """
    candidates = [
        # Playwright profile
        os.path.join(os.getcwd(), ".playwright_profile", "Default", "Network", "Cookies"),
        # Chrome Windows User Data
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Network\Cookies"),
        # Edge Windows User Data
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Network\Cookies"),
    ]

    for db_path in candidates:
        if os.path.isfile(db_path):
            try:
                # Copy db to avoid lock conflicts
                import tempfile
                import shutil
                with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
                    shutil.copyfile(db_path, tmp_db.name)
                    tmp_path = tmp_db.name

                conn = sqlite3.connect(tmp_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, value FROM cookies WHERE host_key LIKE '%google.com%' AND value != ''"
                )
                cookies = [f"{row[0]}={row[1]}" for row in cursor.fetchall() if row[0] and row[1]]
                conn.close()
                os.remove(tmp_path)

                if cookies:
                    logger.debug(f"Detected {len(cookies)} Google cookies from {db_path}")
                    return "; ".join(cookies)
            except Exception as exc:
                logger.debug(f"Could not read cookies from {db_path}: {exc}")
                continue

    return ""


class ScholarHttpClient:
    """Lightweight HTTP client for Google Scholar AJAX endpoints."""

    def __init__(
        self,
        user_agent: str = DEFAULT_SCHOLAR_USER_AGENT,
        cookie: str = "",
        timeout: int = 15,
    ):
        self.user_agent = user_agent
        self.cookie = cookie or detect_local_browser_cookie_header()
        self.timeout = timeout
        self.session = requests.Session()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def is_captcha_or_blocked(self, response: requests.Response) -> bool:
        """Determines whether Google returned a CAPTCHA challenge or rate limiting."""
        if response.status_code in (429, 503):
            return True
        text = response.text.lower()
        if "our systems have detected unusual traffic" in text or "g-recaptcha" in text or "captcha" in text:
            return True
        return False

    def fetch_profile_page(
        self,
        user_id: str,
        start: int = 0,
        page_size: int = 100,
        sort_by: str = "citations",
    ) -> Tuple[Optional[str], bool]:
        """
        Fetches one page of author profile citations.
        Returns: (html_text, is_blocked)
        """
        clean_user = extract_scholar_user_id(user_id)
        if not clean_user:
            return None, False

        params: Dict[str, Any] = {
            "user": clean_user,
            "hl": "en",
            "cstart": start,
            "pagesize": page_size,
        }
        if sort_by == "publication-date" or sort_by == "pubdate":
            params["sortby"] = "pubdate"

        try:
            resp = self.session.get(
                SCHOLAR_BASE_URL,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if self.is_captcha_or_blocked(resp):
                logger.warning(f"Google Scholar returned CAPTCHA / 429 block for user {clean_user}.")
                return None, True
            if resp.status_code == 200:
                return resp.text, False
            logger.warning(f"Scholar HTTP returned status {resp.status_code}")
            return None, False
        except Exception as exc:
            logger.warning(f"Scholar HTTP request failed: {exc}")
            return None, False

    def parse_profile_html(self, html: str, user_id: str) -> ScholarAuthorProfile:
        """Parses scholar profile info, stats table, and paper rows."""
        soup = BeautifulSoup(html, "html.parser")
        profile = ScholarAuthorProfile(user_id=user_id)

        # Name
        name_elem = soup.select_one("#gsc_prf_in")
        if name_elem:
            profile.name = name_elem.text.strip()

        # Affiliation
        aff_elem = soup.select_one(".gsc_prf_il")
        if aff_elem:
            profile.affiliation = aff_elem.text.strip()

        # Interests
        interest_elems = soup.select("#gsc_prf_int a")
        profile.interests = [elem.text.strip() for elem in interest_elems if elem.text.strip()]

        # Stats Table (#gsc_rsb_st)
        stats_rows = soup.select("#gsc_rsb_st tbody tr")
        raw_stats: Dict[str, List[str]] = {}
        for tr in stats_rows:
            label_col = tr.select_one("td.gsc_rsb_sc1, td a.gsc_rsb_f")
            if not label_col:
                label_col = tr.select_one("td")
            values = [td.text.strip() for td in tr.select("td.gsc_rsb_std")]
            if label_col and values:
                label = label_col.text.strip()
                raw_stats[label] = values

        profile.raw_stats = raw_stats
        if "Citations" in raw_stats:
            profile.total_citations = raw_stats["Citations"][0] if len(raw_stats["Citations"]) > 0 else "N/A"
            profile.citations_since_recent = raw_stats["Citations"][1] if len(raw_stats["Citations"]) > 1 else "N/A"
        if "h-index" in raw_stats:
            profile.h_index = raw_stats["h-index"][0] if len(raw_stats["h-index"]) > 0 else "N/A"
            profile.h_index_since_recent = raw_stats["h-index"][1] if len(raw_stats["h-index"]) > 1 else "N/A"
        if "i10-index" in raw_stats:
            profile.i10_index = raw_stats["i10-index"][0] if len(raw_stats["i10-index"]) > 0 else "N/A"
            profile.i10_index_since_recent = raw_stats["i10-index"][1] if len(raw_stats["i10-index"]) > 1 else "N/A"

        # Publications (tr.gsc_a_tr)
        for tr in soup.select("tr.gsc_a_tr"):
            title_elem = tr.select_one(".gsc_a_at")
            if not title_elem:
                continue
            title = title_elem.text.strip()
            detail_href = title_elem.get("href", "")

            # Extract article_id from citation_for_view query param if present
            article_id = ""
            if "citation_for_view=" in detail_href:
                val = detail_href.split("citation_for_view=")[-1].split("&")[0]
                if ":" in val:
                    article_id = val.split(":")[-1]
                else:
                    article_id = val

            meta_elems = tr.select(".gsc_a_t .gs_gray")
            authors = meta_elems[0].text.strip() if len(meta_elems) > 0 else "N/A"
            venue = meta_elems[1].text.strip() if len(meta_elems) > 1 else "N/A"

            citation_elem = tr.select_one(".gsc_a_ac")
            citations = citation_elem.text.strip() if citation_elem and citation_elem.text.strip() else "0"
            if citations == "":
                citations = "0"

            year_elem = tr.select_one(".gsc_a_y")
            year = year_elem.text.strip() if year_elem and year_elem.text.strip() else "N/A"

            pub_record = {
                "Title": title,
                "Authors": authors,
                "Journal/Venue": venue,
                "Citations": citations,
                "Year": year,
                "Scholar Article ID": article_id,
                "Scholar Detail URL": f"https://scholar.google.com{detail_href}" if detail_href.startswith("/") else detail_href,
                "Scholar Author Citations": profile.total_citations,
                "Scholar Author Citations (Recent)": profile.citations_since_recent,
                "Scholar Author H-Index": profile.h_index,
                "Scholar Author H-Index (Recent)": profile.h_index_since_recent,
                "Scholar Author i10-Index": profile.i10_index,
                "Scholar Author i10-Index (Recent)": profile.i10_index_since_recent,
            }
            profile.publications.append(pub_record)

        return profile

    def fetch_citation_details_fast(self, user_id: str, article_id: str) -> Dict[str, str]:
        """
        Directly fetches single paper metadata without opening browser modal.
        Returns extracted fields (Journal, Volume, Issue, Pages, Publisher, Description, etc.)
        """
        clean_user = extract_scholar_user_id(user_id)
        if not clean_user or not article_id:
            return {}

        params = {
            "view_op": "view_citation",
            "hl": "en",
            "user": clean_user,
            "citation_for_view": f"{clean_user}:{article_id}",
        }
        try:
            resp = self.session.get(
                SCHOLAR_BASE_URL,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            if resp.status_code == 200 and not self.is_captcha_or_blocked(resp):
                soup = BeautifulSoup(resp.text, "html.parser")
                fields: Dict[str, str] = {}
                field_names = [elem.text.strip() for elem in soup.select(".gsc_oci_field")]
                field_vals = [elem.text.strip() for elem in soup.select(".gsc_oci_value")]
                for k, v in zip(field_names, field_vals):
                    if k and v:
                        fields[k] = v
                return fields
        except Exception as exc:
            logger.debug(f"Failed to fetch fast citation details for {article_id}: {exc}")
        return {}

    def fetch_all_profile_records_fast(
        self,
        user_id: str,
        max_records: int = 0,
        sort_by: str = "citations",
    ) -> Tuple[Optional[ScholarAuthorProfile], bool]:
        """
        Paginates through profile pages using cstart and pagesize=100.
        Returns (ScholarAuthorProfile, is_blocked)
        """
        clean_user = extract_scholar_user_id(user_id)
        if not clean_user:
            return None, False

        start = 0
        page_size = 100
        aggregated_profile: Optional[ScholarAuthorProfile] = None

        while True:
            logger.info(f"Scholar Fast-Path: requesting records {start} to {start + page_size}...")
            html, is_blocked = self.fetch_profile_page(
                clean_user,
                start=start,
                page_size=page_size,
                sort_by=sort_by,
            )
            if is_blocked:
                return None, True
            if not html:
                break

            current_page_profile = self.parse_profile_html(html, clean_user)
            if not current_page_profile.publications:
                break

            if aggregated_profile is None:
                aggregated_profile = current_page_profile
            else:
                aggregated_profile.publications.extend(current_page_profile.publications)

            num_fetched = len(current_page_profile.publications)
            logger.info(f"Scholar Fast-Path: extracted {num_fetched} papers in current chunk.")

            # If fewer records returned than page_size or reached user limit, stop
            if num_fetched < page_size:
                break
            if max_records and len(aggregated_profile.publications) >= max_records:
                aggregated_profile.publications = aggregated_profile.publications[:max_records]
                break

            start += page_size
            time.sleep(0.3)  # Polite gap between page requests

        return aggregated_profile, False

# -*- coding: utf-8 -*-
"""
Google Scholar Labs Client for nature-impact.
Implements the binary streaming protocol and XSRF token discovery for Google Scholar Labs AI search.
"""

from __future__ import annotations

import json
import logging
import re
import struct
import urllib.parse
from typing import Any, Dict, List, Optional, TypedDict

import requests

logger = logging.getLogger(__name__)

SCHOLAR_LABS_BASE = "https://scholar.google.com/scholar_labs"
SCHOLAR_LABS_SESSION_URL = "https://scholar.google.com/scholar_labs/search/session_data"


class ScholarLabsSearchResult(TypedDict, total=False):
    title: str
    authors: str
    abstract: str
    citation_count: int
    url: str
    paper_id: str
    raw_html: str


class ScholarLabsChunk(TypedDict, total=False):
    state: int
    status: str
    results: List[ScholarLabsSearchResult]
    suggested_questions: List[str]


def parse_stream(data: bytes) -> List[ScholarLabsChunk]:
    """
    Parses Google Scholar Labs binary streaming response.
    Each chunk is framed with a 4-byte big-endian uint32 length header followed by JSON payload.
    """
    chunks: List[ScholarLabsChunk] = []
    offset = 0

    while offset + 4 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        offset += 4

        if offset + length > len(data):
            break

        raw_chunk = data[offset : offset + length]
        offset += length

        try:
            obj = json.loads(raw_chunk.decode("utf-8"))
            if isinstance(obj, dict):
                chunks.append(obj)
        except Exception as exc:
            logger.debug(f"Failed to parse chunk JSON: {exc}")
            continue

    return chunks


def extract_xsrf_token(page_text: str) -> Optional[str]:
    """Extracts Scholar Labs XSRF token from HTML page response."""
    if not page_text:
        return None

    # Pattern 1: URL query param (?xsrf=... or &xsrf=...)
    match = re.search(r"[?&]xsrf=([^\"'&<>\s\\]+)", page_text)
    if match:
        return match.group(1)

    # Pattern 2: JSON/JS variable or data attribute
    patterns = [
        re.compile(r"""["']xsrf["']\s*[:=]\s*["']([^"'<>\\\s]+)["']"""),
        re.compile(r"""data-xsrf=["']([^"'<>\\\s]+)["']"""),
        re.compile(r"""_xsrf\s*=\s*["']([^"'<>\\\s]+)["']"""),
    ]
    for pattern in patterns:
        m = pattern.search(page_text)
        if m:
            return m.group(1)

    return None


class ScholarLabsClient:
    """HTTP client for Google Scholar Labs streaming search API."""

    def __init__(
        self,
        cookie: str = "",
        xsrf_token: str = "",
        hl: str = "en",
        timeout: int = 45,
    ):
        self.cookie = cookie
        self.xsrf_token = xsrf_token
        self.hl = hl
        self.timeout = timeout
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            "Referer": "https://scholar.google.com/scholar_labs/search",
            "Origin": "https://scholar.google.com",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Accept": "*/*",
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def discover_xsrf_token(self) -> Optional[str]:
        """Fetches the Scholar Labs search landing page to discover XSRF token."""
        try:
            url = f"{SCHOLAR_LABS_BASE}/search?hl={self.hl}"
            resp = self.session.get(url, headers=self._headers(), timeout=15)
            if resp.status_code == 200:
                token = extract_xsrf_token(resp.text)
                if token:
                    self.xsrf_token = token
                    return token
        except Exception as exc:
            logger.debug(f"Failed to discover XSRF token: {exc}")
        return None

    def search(self, query: str) -> List[ScholarLabsChunk]:
        """
        Executes a Scholar Labs AI literature search query and returns parsed chunks.
        """
        if not query or not query.strip():
            return []

        if not self.xsrf_token:
            self.discover_xsrf_token()

        url = SCHOLAR_LABS_SESSION_URL
        params = {"hl": self.hl}
        if self.xsrf_token:
            params["xsrf"] = self.xsrf_token

        body = {
            "q": query.strip(),
            "hl": self.hl,
        }
        if self.xsrf_token:
            body["xsrf"] = self.xsrf_token

        try:
            resp = self.session.post(
                url,
                params=params,
                data=body,
                headers=self._headers(),
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return parse_stream(resp.content)
            logger.warning(f"Scholar Labs request returned HTTP {resp.status_code}")
        except Exception as exc:
            logger.warning(f"Scholar Labs search request failed: {exc}")

        return []

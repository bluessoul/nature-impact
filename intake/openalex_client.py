# -*- coding: utf-8 -*-
"""
OpenAlex API Client for nature-impact.
Provides robust HTTP access with polite QPS rate limiting, exponential backoff retries,
safe API key handling, and batch DOI queries.
"""

from __future__ import annotations

import logging
import os
import re
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"
DEFAULT_USER_AGENT = "nature-impact/2.0 (mailto:scholar_scraper@example.com)"
MAX_RETRIES = 4
DEFAULT_TIMEOUT = 25

OPENALEX_WORK_SELECT = ",".join([
    "id",
    "doi",
    "ids",
    "title",
    "display_name",
    "publication_year",
    "publication_date",
    "authorships",
    "corresponding_author_ids",
    "biblio",
    "primary_location",
    "locations",
    "best_oa_location",
    "type",
    "cited_by_count",
])

OPENALEX_AUTHOR_SELECT = ",".join([
    "id",
    "display_name",
    "last_known_institutions",
    "works_count",
    "orcid",
])


class RateLimiter:
    """Simple token/timestamp based rate limiter ensuring polite intervals between requests."""

    def __init__(self, qps: float = 8.0):
        self.interval = 1.0 / max(0.1, qps)
        self._last_call = 0.0

    def wait(self) -> None:
        now = time.time()
        elapsed = now - self._last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self._last_call = time.time()


class OpenAlexClient:
    """Client for OpenAlex REST API with polite rate-limiting, retries, and batch querying."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        email: Optional[str] = None,
        qps: Optional[float] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.api_key = api_key or os.getenv("OPENALEX_API_KEY", "")
        self.email = email or os.getenv("OPENALEX_EMAIL", "")
        
        # When an API key is available, OpenAlex allows higher throughput (up to 100 QPS)
        # Without key, polite pool is recommended around 5-10 QPS
        default_qps = 15.0 if self.api_key else 8.0
        self.qps = qps if qps is not None else default_qps
        self.limiter = RateLimiter(self.qps)
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        if self.email:
            headers["User-Agent"] = f"nature-impact/2.0 (mailto:{self.email})"
        return headers

    def _build_url_with_api_key(self, url: str) -> str:
        """Appends the api_key query parameter to url if present, keeping logs clean."""
        if not self.api_key:
            return url
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{urllib.parse.urlencode({'api_key': self.api_key})}"

    def fetch_with_retry(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Fetches data from OpenAlex with exponential backoff on 429/5xx errors."""
        retries = max_retries if max_retries is not None else self.max_retries
        params = dict(params or {})
        
        # Remove api_key from params dict if passed, use dedicated URL appending
        params.pop("api_key", None)
        query_str = urllib.parse.urlencode(params, doseq=True) if params else ""
        clean_url = f"{url}?{query_str}" if query_str else url
        authed_url = self._build_url_with_api_key(clean_url)

        headers = self._headers()
        backoff = 1.0

        for attempt in range(1, retries + 1):
            self.limiter.wait()
            try:
                response = self.session.get(authed_url, headers=headers, timeout=self.timeout)
                status = response.status_code

                if status == 200:
                    return response.json()

                if status == 404:
                    logger.debug(f"OpenAlex 404 Not Found for URL: {clean_url}")
                    return None

                if status == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = float(retry_after) if retry_after and retry_after.isdigit() else backoff * 2.0
                    logger.warning(
                        f"OpenAlex rate limit (429) hit on attempt {attempt}/{retries}. "
                        f"Backing off for {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    backoff *= 2.0
                    continue

                if status in (500, 502, 503, 504):
                    logger.warning(
                        f"OpenAlex server error ({status}) on attempt {attempt}/{retries}. "
                        f"Retrying in {backoff:.1f}s..."
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue

                # Other non-retriable 4xx client errors (e.g. 400, 401, 403)
                logger.error(f"OpenAlex client error {status} for {clean_url}: {response.text[:200]}")
                return None

            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as exc:
                if attempt == retries:
                    logger.warning(f"OpenAlex request failed after {retries} attempts for {clean_url}: {exc}")
                    return None
                logger.debug(f"OpenAlex connection error ({exc}), retrying in {backoff:.1f}s...")
                time.sleep(backoff)
                backoff *= 2.0

        return None

    def search_authors(
        self,
        name: str,
        per_page: int = 5,
        select: Optional[str] = OPENALEX_AUTHOR_SELECT,
    ) -> List[Dict[str, Any]]:
        """Searches author entities by name."""
        if not name or not name.strip():
            return []
        url = f"{BASE_URL}/authors"
        params: Dict[str, Any] = {
            "search": name.strip(),
            "per_page": max(1, min(per_page, 50)),
        }
        if select:
            params["select"] = select
        data = self.fetch_with_retry(url, params)
        if not data:
            return []
        return data.get("results", [])

    def get_works(
        self,
        params: Dict[str, Any],
        select: Optional[str] = OPENALEX_WORK_SELECT,
    ) -> List[Dict[str, Any]]:
        """Queries works endpoint with custom parameters."""
        url = f"{BASE_URL}/works"
        request_params = dict(params)
        if select and "select" not in request_params:
            request_params["select"] = select
        data = self.fetch_with_retry(url, request_params)
        if not data:
            return []
        return data.get("results", [])

    def search_works_by_title(
        self,
        title: str,
        per_page: int = 3,
        select: Optional[str] = OPENALEX_WORK_SELECT,
    ) -> List[Dict[str, Any]]:
        """Searches works by publication title."""
        if not title or not title.strip():
            return []
        return self.get_works({"search": title.strip(), "per-page": per_page}, select=select)

    def get_work_by_doi(
        self,
        doi: str,
        select: Optional[str] = OPENALEX_WORK_SELECT,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a single work by its DOI."""
        clean = self.normalize_doi(doi)
        if not clean:
            return None
        doi_url = f"https://doi.org/{clean}"
        results = self.get_works({"filter": f"doi:{doi_url}", "per-page": 1}, select=select)
        return results[0] if results else None

    def batch_get_works_by_dois(
        self,
        dois: List[str],
        chunk_size: int = 50,
        select: Optional[str] = OPENALEX_WORK_SELECT,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Batch retrieves multiple works using OpenAlex pipe-delimited DOI filtering.
        Returns a mapping of normalized DOI -> parsed work dict.
        """
        results_by_doi: Dict[str, Dict[str, Any]] = {}
        normalized_dois = [self.normalize_doi(d) for d in dois if self.normalize_doi(d)]
        unique_dois = list(dict.fromkeys(normalized_dois))

        if not unique_dois:
            return results_by_doi

        for i in range(0, len(unique_dois), chunk_size):
            chunk = unique_dois[i : i + chunk_size]
            doi_urls = [f"https://doi.org/{d}" for d in chunk]
            filter_val = f"doi:{'|'.join(doi_urls)}"
            
            works = self.get_works({"filter": filter_val, "per-page": len(chunk)}, select=select)
            for work in works:
                work_doi = self.normalize_doi(work.get("doi") or (work.get("ids") or {}).get("doi", ""))
                if work_doi:
                    results_by_doi[work_doi] = work

        return results_by_doi

    @staticmethod
    def normalize_doi(value: Any) -> str:
        """Extracts and normalizes raw DOI string."""
        if not value:
            return ""
        text = str(value).strip()
        text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^doi:\s*", "", text, flags=re.IGNORECASE)
        match = re.search(r"\b10\.\d{4,9}/[^\s\"<>]+", text, flags=re.IGNORECASE)
        if match:
            return match.group(0).rstrip(".,;)")
        return ""


# Shared default singleton instance for lightweight use
_DEFAULT_CLIENT: Optional[OpenAlexClient] = None


def get_default_openalex_client() -> OpenAlexClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = OpenAlexClient()
    return _DEFAULT_CLIENT

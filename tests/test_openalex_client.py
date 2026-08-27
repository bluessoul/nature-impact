# -*- coding: utf-8 -*-
import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intake.openalex_client import (
    OpenAlexClient,
    RateLimiter,
    OPENALEX_WORK_SELECT,
    OPENALEX_AUTHOR_SELECT,
)
from scholar_playwright import (
    enrich_record_with_openalex,
    enrich_records_with_openalex_batch,
    parse_openalex_work,
)


class TestOpenAlexClient(unittest.TestCase):
    def test_rate_limiter_spacing(self):
        limiter = RateLimiter(qps=20.0)  # 50ms interval
        start = time.time()
        limiter.wait()
        limiter.wait()
        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.04)

    def test_normalize_doi(self):
        self.assertEqual(OpenAlexClient.normalize_doi("https://doi.org/10.1016/j.polymdegradstab.2021.109612"), "10.1016/j.polymdegradstab.2021.109612")
        self.assertEqual(OpenAlexClient.normalize_doi("http://dx.doi.org/10.1002/advs.202201000"), "10.1002/advs.202201000")
        self.assertEqual(OpenAlexClient.normalize_doi("doi: 10.1038/s41586-020-2649-2"), "10.1038/s41586-020-2649-2")
        self.assertEqual(OpenAlexClient.normalize_doi("invalid_doi_text"), "")
        self.assertEqual(OpenAlexClient.normalize_doi(""), "")

    def test_build_url_with_api_key(self):
        client_no_key = OpenAlexClient(api_key="")
        self.assertEqual(
            client_no_key._build_url_with_api_key("https://api.openalex.org/works?search=test"),
            "https://api.openalex.org/works?search=test",
        )

        client_with_key = OpenAlexClient(api_key="secret_key_123")
        self.assertEqual(
            client_with_key._build_url_with_api_key("https://api.openalex.org/works?search=test"),
            "https://api.openalex.org/works?search=test&api_key=secret_key_123",
        )
        self.assertEqual(
            client_with_key._build_url_with_api_key("https://api.openalex.org/works"),
            "https://api.openalex.org/works?api_key=secret_key_123",
        )

    @patch("requests.Session.get")
    def test_fetch_with_retry_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"id": "W123"}]}
        mock_get.return_value = mock_resp

        client = OpenAlexClient(qps=100.0)
        data = client.fetch_with_retry("https://api.openalex.org/works", {"search": "fire"})
        self.assertIsNotNone(data)
        self.assertEqual(data["results"][0]["id"], "W123")
        self.assertEqual(mock_get.call_count, 1)

    @patch("time.sleep", return_value=None)
    @patch("requests.Session.get")
    def test_fetch_with_retry_on_429(self, mock_get, mock_sleep):
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.headers = {"Retry-After": "1"}

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {"results": [{"id": "W456"}]}

        mock_get.side_effect = [mock_resp_429, mock_resp_200]

        client = OpenAlexClient(qps=100.0, max_retries=3)
        data = client.fetch_with_retry("https://api.openalex.org/works", {"search": "fire"})
        self.assertIsNotNone(data)
        self.assertEqual(data["results"][0]["id"], "W456")
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called()

    @patch("requests.Session.get")
    def test_batch_get_works_by_dois(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1000/1", "title": "Paper 1"},
                {"id": "https://openalex.org/W2", "doi": "https://doi.org/10.1000/2", "title": "Paper 2"},
            ]
        }
        mock_get.return_value = mock_resp

        client = OpenAlexClient(qps=100.0)
        results = client.batch_get_works_by_dois(["10.1000/1", "https://doi.org/10.1000/2"])
        self.assertEqual(len(results), 2)
        self.assertIn("10.1000/1", results)
        self.assertIn("10.1000/2", results)
        self.assertEqual(results["10.1000/1"]["title"], "Paper 1")

    def test_enrich_records_with_openalex_batch(self):
        records = [
            {
                "Title": "Paper with DOI",
                "DOI": "10.1000/1",
                "Authors": "Alice, Bob",
            },
            {
                "Title": "Paper without DOI but searchable title",
                "DOI": "",
                "Authors": "Charlie...",
            },
        ]

        mock_work_1 = {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1000/1",
            "title": "Paper with DOI",
            "publication_year": 2023,
            "authorships": [
                {"author": {"id": "A1", "display_name": "Alice"}, "is_corresponding": True},
                {"author": {"id": "A2", "display_name": "Bob"}, "is_corresponding": False},
            ],
            "biblio": {"volume": "10", "issue": "2", "first_page": "100", "last_page": "110"},
            "primary_location": {"source": {"display_name": "Nature Materials", "publisher": "Nature"}},
        }

        mock_work_2 = {
            "id": "https://openalex.org/W2",
            "doi": "https://doi.org/10.1000/2",
            "title": "Paper without DOI but searchable title",
            "publication_year": 2024,
            "authorships": [
                {"author": {"id": "A3", "display_name": "Charlie Chaplin"}, "is_corresponding": False},
                {"author": {"id": "A4", "display_name": "David Bowie"}, "is_corresponding": True},
            ],
            "biblio": {"volume": "5", "issue": "1", "first_page": "1", "last_page": "9"},
            "primary_location": {"source": {"display_name": "Science", "publisher": "AAAS"}},
        }

        client = OpenAlexClient(qps=100.0)
        with patch.object(client, "batch_get_works_by_dois", return_value={"10.1000/1": mock_work_1}), \
             patch.object(client, "search_works_by_title", return_value=[mock_work_2]):

            with patch("scholar_playwright.get_default_openalex_client", return_value=client):
                enrich_records_with_openalex_batch(records)

        # Verify Record 1 (DOI Batch)
        self.assertEqual(records[0]["OpenAlex ID"], "https://openalex.org/W1")
        self.assertEqual(records[0]["OpenAlex Match Method"], "doi_batch")
        self.assertEqual(records[0]["OpenAlex Corresponding Authors"], "Alice")
        self.assertEqual(records[0]["OpenAlex Corresponding Author Positions"], "1")
        self.assertEqual(records[0]["Volume"], "10")
        self.assertEqual(records[0]["Issue"], "2")
        self.assertEqual(records[0]["Pages"], "100-110")

        # Verify Record 2 (Title Fallback)
        self.assertEqual(records[1]["OpenAlex ID"], "https://openalex.org/W2")
        self.assertEqual(records[1]["OpenAlex Match Method"], "title")
        self.assertEqual(records[1]["Authors"], "Charlie Chaplin, David Bowie")
        self.assertEqual(records[1]["OpenAlex Corresponding Authors"], "David Bowie")
        self.assertEqual(records[1]["OpenAlex Corresponding Author Positions"], "2")
        self.assertEqual(records[1]["Journal/Venue"], "Science")


if __name__ == "__main__":
    unittest.main()

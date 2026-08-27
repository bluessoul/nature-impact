# -*- coding: utf-8 -*-
import json
import os
import struct
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intake.scholar_labs_client import (
    ScholarLabsClient,
    extract_xsrf_token,
    parse_stream,
)


class TestScholarLabsClient(unittest.TestCase):
    def test_parse_stream_binary_framing(self):
        chunk1 = {"state": 1, "results": [{"title": "Transformer Model", "authors": "Vaswani et al."}]}
        chunk2 = {"state": 2, "suggested_questions": ["What is attention?", "How to train LLMs?"]}

        b1 = json.dumps(chunk1).encode("utf-8")
        b2 = json.dumps(chunk2).encode("utf-8")

        # Frame with 4-byte big-endian prefix
        stream_data = struct.pack(">I", len(b1)) + b1 + struct.pack(">I", len(b2)) + b2

        parsed = parse_stream(stream_data)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["results"][0]["title"], "Transformer Model")
        self.assertEqual(parsed[1]["suggested_questions"][0], "What is attention?")

    def test_extract_xsrf_token(self):
        html_query = '<a href="/scholar_labs/search?hl=en&xsrf=TOKEN_ABC_123">Search</a>'
        self.assertEqual(extract_xsrf_token(html_query), "TOKEN_ABC_123")

        html_data = '<div data-xsrf="TOKEN_DEF_456"></div>'
        self.assertEqual(extract_xsrf_token(html_data), "TOKEN_DEF_456")

        html_js = 'var config = {"xsrf": "TOKEN_GHI_789"};'
        self.assertEqual(extract_xsrf_token(html_js), "TOKEN_GHI_789")

        self.assertIsNone(extract_xsrf_token(""))

    @patch("requests.Session.post")
    def test_scholar_labs_search(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        chunk = {"state": 1, "results": [{"title": "Diffusion Models", "citation_count": 5000}]}
        raw_payload = json.dumps(chunk).encode("utf-8")
        mock_resp.content = struct.pack(">I", len(raw_payload)) + raw_payload
        mock_post.return_value = mock_resp

        client = ScholarLabsClient(xsrf_token="TEST_XSRF")
        results = client.search("Diffusion Models")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["results"][0]["title"], "Diffusion Models")
        self.assertEqual(results[0]["results"][0]["citation_count"], 5000)


if __name__ == "__main__":
    unittest.main()

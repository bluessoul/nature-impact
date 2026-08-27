# -*- coding: utf-8 -*-
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intake.scholar_http_client import (
    ScholarHttpClient,
    extract_scholar_user_id,
    detect_local_browser_cookie_header,
)


class TestScholarHttpClient(unittest.TestCase):
    def test_extract_scholar_user_id(self):
        self.assertEqual(
            extract_scholar_user_id("https://scholar.google.com/citations?user=u8ZwRT4AAAAJ&hl=en"),
            "u8ZwRT4AAAAJ"
        )
        self.assertEqual(
            extract_scholar_user_id("citations?hl=en&user=abcDEF1AAAAJ"),
            "abcDEF1AAAAJ"
        )
        self.assertEqual(
            extract_scholar_user_id("u8ZwRT4AAAAJ"),
            "u8ZwRT4AAAAJ"
        )
        self.assertEqual(extract_scholar_user_id(""), "")

    def test_parse_profile_html(self):
        sample_html = """
        <html>
        <body>
            <div id="gsc_prf_in">Prof. Jane Doe</div>
            <div class="gsc_prf_il">Institute of Advanced Materials</div>
            <div id="gsc_prf_int"><a href="#">Nanotechnology</a><a href="#">Polymers</a></div>
            <table id="gsc_rsb_st">
                <tbody>
                    <tr><td class="gsc_rsb_sc1"><a class="gsc_rsb_f" href="#">Citations</a></td><td class="gsc_rsb_std">5000</td><td class="gsc_rsb_std">4200</td></tr>
                    <tr><td class="gsc_rsb_sc1"><a class="gsc_rsb_f" href="#">h-index</a></td><td class="gsc_rsb_std">38</td><td class="gsc_rsb_std">35</td></tr>
                    <tr><td class="gsc_rsb_sc1"><a class="gsc_rsb_f" href="#">i10-index</a></td><td class="gsc_rsb_std">70</td><td class="gsc_rsb_std">65</td></tr>
                </tbody>
            </table>
            <table>
                <tr class="gsc_a_tr">
                    <td class="gsc_a_t">
                        <a class="gsc_a_at" href="/citations?view_op=view_citation&hl=en&user=u8ZwRT4AAAAJ&citation_for_view=u8ZwRT4AAAAJ:u5HHmVD_uO8C">High performance nanocomposites</a>
                        <div class="gs_gray">J Doe, A Smith, B Brown</div>
                        <div class="gs_gray">Nature Materials 12 (4), 100-108, 2021</div>
                    </td>
                    <td class="gsc_a_c"><a class="gsc_a_ac" href="#">150</a></td>
                    <td class="gsc_a_y"><span class="gsc_a_h">2021</span></td>
                </tr>
            </table>
        </body>
        </html>
        """
        client = ScholarHttpClient()
        profile = client.parse_profile_html(sample_html, "u8ZwRT4AAAAJ")

        self.assertEqual(profile.name, "Prof. Jane Doe")
        self.assertEqual(profile.affiliation, "Institute of Advanced Materials")
        self.assertEqual(profile.interests, ["Nanotechnology", "Polymers"])
        self.assertEqual(profile.total_citations, "5000")
        self.assertEqual(profile.citations_since_recent, "4200")
        self.assertEqual(profile.h_index, "38")
        self.assertEqual(profile.i10_index, "70")

        self.assertEqual(len(profile.publications), 1)
        pub = profile.publications[0]
        self.assertEqual(pub["Title"], "High performance nanocomposites")
        self.assertEqual(pub["Authors"], "J Doe, A Smith, B Brown")
        self.assertEqual(pub["Journal/Venue"], "Nature Materials 12 (4), 100-108, 2021")
        self.assertEqual(pub["Citations"], "150")
        self.assertEqual(pub["Year"], "2021")
        self.assertEqual(pub["Scholar Article ID"], "u5HHmVD_uO8C")

    def test_is_captcha_or_blocked(self):
        client = ScholarHttpClient()
        
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.text = "Too many requests"
        self.assertTrue(client.is_captcha_or_blocked(mock_429))

        mock_captcha = MagicMock()
        mock_captcha.status_code = 200
        mock_captcha.text = "Please solve the g-recaptcha to continue"
        self.assertTrue(client.is_captcha_or_blocked(mock_captcha))

        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.text = "<html><body>Profile Page</body></html>"
        self.assertFalse(client.is_captcha_or_blocked(mock_ok))

    @patch("requests.Session.get")
    def test_fetch_citation_details_fast(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <html><body>
            <div id="gsc_oci_title">Sample Paper Title</div>
            <div class="gsc_oci_field">Authors</div><div class="gsc_oci_value">Alice, Bob</div>
            <div class="gsc_oci_field">Journal</div><div class="gsc_oci_value">Science Advances</div>
            <div class="gsc_oci_field">Volume</div><div class="gsc_oci_value">8</div>
            <div class="gsc_oci_field">Pages</div><div class="gsc_oci_value">10-20</div>
        </body></html>
        """
        mock_get.return_value = mock_resp

        client = ScholarHttpClient()
        fields = client.fetch_citation_details_fast("u8ZwRT4AAAAJ", "art123")
        self.assertEqual(fields.get("Authors"), "Alice, Bob")
        self.assertEqual(fields.get("Journal"), "Science Advances")
        self.assertEqual(fields.get("Volume"), "8")
        self.assertEqual(fields.get("Pages"), "10-20")


if __name__ == "__main__":
    unittest.main()

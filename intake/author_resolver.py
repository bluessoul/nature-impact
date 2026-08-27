from __future__ import annotations

from urllib.parse import quote

import requests


from intake.openalex_client import get_default_openalex_client

OPENALEX_AUTHORS_URL = "https://api.openalex.org/authors"


def resolve_author(profile: dict, search_func=None, min_confidence: float = 0.78, conflict_margin: float = 0.08) -> dict:
    """Resolve an intake profile to candidate author identities."""

    candidates: list[dict] = []
    if profile.get("scholar_user_id"):
        candidates.append({
            "source": "google_scholar",
            "id": profile["scholar_user_id"],
            "url": profile.get("scholar_url") or f"https://scholar.google.com/citations?user={profile['scholar_user_id']}",
            "display_name": profile.get("name", ""),
            "confidence": 1.0,
            "evidence": ["Scholar ID provided in input material"],
        })
    if profile.get("orcid"):
        candidates.append({
            "source": "orcid",
            "id": profile["orcid"],
            "url": f"https://orcid.org/{profile['orcid']}",
            "display_name": profile.get("name", ""),
            "confidence": 0.95,
            "evidence": ["ORCID iD provided in input material"],
        })

    if not candidates and profile.get("name"):
        search = search_func or search_openalex_authors
        candidates.extend(score_openalex_candidates(search(profile["name"]), profile))

    candidates = sorted(candidates, key=lambda item: item.get("confidence", 0), reverse=True)
    status = "needs_user_confirmation"
    accepted = candidates[0] if candidates else None
    if accepted:
        if accepted["source"] == "google_scholar":
            status = "ready"
            return {
                "status": status,
                "accepted_candidate": accepted,
                "candidates": candidates,
                "needs_confirmation": False,
            }
        runner_ready = accepted["source"] in {"google_scholar", "orcid"} or bool(profile.get("orcid"))
        second = candidates[1]["confidence"] if len(candidates) > 1 else 0
        if accepted["confidence"] >= min_confidence and accepted["confidence"] - second < conflict_margin:
            status = "needs_user_confirmation"
        elif accepted["confidence"] >= min_confidence and runner_ready:
            status = "ready"
        elif accepted["confidence"] >= min_confidence:
            status = "identity_found_no_runnable_id"

    return {
        "status": status,
        "accepted_candidate": accepted if status == "ready" else None,
        "candidates": candidates,
        "needs_confirmation": status != "ready",
    }


def search_openalex_authors(name: str, per_page: int = 5) -> list[dict]:
    client = get_default_openalex_client()
    return client.search_authors(name, per_page=per_page)


def score_openalex_candidates(results: list[dict], profile: dict) -> list[dict]:
    scored = []
    for result in results:
        confidence, evidence = score_openalex_candidate(result, profile)
        scored.append({
            "source": "openalex",
            "id": result.get("id", ""),
            "url": result.get("id", ""),
            "display_name": result.get("display_name", ""),
            "confidence": round(confidence, 3),
            "evidence": evidence,
            "raw": result,
        })
    return scored


def score_openalex_candidate(candidate: dict, profile: dict) -> tuple[float, list[str]]:
    evidence: list[str] = []
    score = 0.0
    query_name = normalize(profile.get("name", ""))
    display_name = normalize(candidate.get("display_name", ""))
    if query_name and display_name:
        if query_name == display_name:
            score += 0.42
            evidence.append("Exact name match")
        elif set(query_name.split()) <= set(display_name.split()) or set(display_name.split()) <= set(query_name.split()):
            score += 0.32
            evidence.append("Partial name-token match")

    affiliation = normalize(profile.get("affiliation", ""))
    last_institutions = candidate.get("last_known_institutions") or []
    institution_names = [normalize(item.get("display_name", "")) for item in last_institutions]
    if affiliation and any(affiliation in name or name in affiliation for name in institution_names if name):
        score += 0.28
        evidence.append("Affiliation matches OpenAlex last known institution")

    input_titles = {normalize(title) for title in profile.get("publication_titles", []) if title}
    work_titles = {normalize(work.get("title", "")) for work in candidate.get("works", []) if work.get("title")}
    overlap = title_overlap(input_titles, work_titles)
    if overlap:
        score += min(0.22, 0.08 * len(overlap))
        evidence.append(f"Publication title overlap: {len(overlap)}")

    if candidate.get("orcid") and profile.get("orcid") and profile["orcid"] in candidate["orcid"]:
        score += 0.35
        evidence.append("ORCID cross-link matches")
    elif candidate.get("orcid"):
        score += 0.06
        evidence.append("OpenAlex candidate has ORCID")

    if candidate.get("works_count", 0):
        score += 0.02
    return min(score, 0.99), evidence or ["Weak name-only match"]


def title_overlap(left: set[str], right: set[str]) -> list[str]:
    overlap = []
    for lhs in left:
        if not lhs:
            continue
        lhs_tokens = set(lhs.split())
        for rhs in right:
            rhs_tokens = set(rhs.split())
            if len(lhs_tokens & rhs_tokens) >= min(5, max(2, len(lhs_tokens) // 2)):
                overlap.append(lhs)
                break
    return overlap


def normalize(value: str) -> str:
    return " ".join((value or "").lower().replace(",", " ").split())


def openalex_author_url(name: str) -> str:
    return f"{OPENALEX_AUTHORS_URL}?search={quote(name)}&per-page=5"

"""
Greenhouse and Lever ATS scrapers.
Both have public JSON APIs — no authentication, no JS rendering needed.
"""

from datetime import datetime
from .base import BaseScraper, Listing

KEYWORDS = {"intern", "internship"}


def _is_intern(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in KEYWORDS)


def _austin(location: str) -> bool:
    loc = location.lower()
    # "In-Office" / "On-site" means the company's own offices — accept it since
    # we only add companies to greenhouse_boards / lever_boards if they have Austin offices.
    return any(x in loc for x in (
        "austin", "tx", "texas", "remote", "anywhere",
        "united states", "us", "in-office", "on-site", "onsite", "in office",
    )) or loc.strip() == ""


class GreenhouseScraper(BaseScraper):
    """
    Hits the public Greenhouse boards API for a list of company slugs.
    API: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
    """

    def search(self, keyword: str) -> list[Listing]:
        return []  # search_all_boards() is the main entry point

    def search_all_boards(self) -> list[Listing]:
        slugs = self.config.get("greenhouse_boards", [])
        results = []
        seen = set()
        for entry in slugs:
            slug = entry["slug"]
            company = entry.get("name", slug)
            listings = self._fetch_board(slug, company)
            for l in listings:
                if l.url not in seen:
                    seen.add(l.url)
                    results.append(l)
        return results

    def _fetch_board(self, slug: str, company: str) -> list[Listing]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
        resp = self._get(url)
        if not resp:
            return []
        try:
            data = resp.json()
        except Exception:
            return []

        results = []
        for job in data.get("jobs", []):
            title = job.get("title", "")
            if not _is_intern(title):
                continue
            location = job.get("location", {}).get("name", "")
            if not _austin(location):
                continue
            job_id = str(job.get("id", ""))
            job_url = job.get("absolute_url") or f"https://boards.greenhouse.io/{slug}/jobs/{job_id}"
            results.append(Listing(
                title=title,
                company=company,
                location=location or "Austin, TX",
                url=job_url,
                source="Greenhouse",
                date_posted=datetime.now(),
                job_id=job_id,
            ))
        return results


class LeverScraper(BaseScraper):
    """
    Hits the public Lever postings API for a list of company slugs.
    API: https://api.lever.co/v0/postings/{slug}?type=internship
    """

    def search(self, keyword: str) -> list[Listing]:
        return []

    def search_all_boards(self) -> list[Listing]:
        slugs = self.config.get("lever_boards", [])
        results = []
        seen = set()
        for entry in slugs:
            slug = entry["slug"]
            company = entry.get("name", slug)
            listings = self._fetch_board(slug, company)
            for l in listings:
                if l.url not in seen:
                    seen.add(l.url)
                    results.append(l)
        return results

    def _fetch_board(self, slug: str, company: str) -> list[Listing]:
        results = []
        for commitment in ("Internship", "intern", ""):
            params = {"mode": "json"}
            if commitment:
                params["commitment"] = commitment
            url = f"https://api.lever.co/v0/postings/{slug}"
            resp = self._get(url, params=params)
            if not resp:
                continue
            try:
                jobs = resp.json()
            except Exception:
                continue
            if not isinstance(jobs, list):
                continue
            for job in jobs:
                title = job.get("text", "")
                if not _is_intern(title):
                    continue
                categories = job.get("categories", {})
                location = categories.get("location", "") or job.get("workplaceType", "")
                if not _austin(location):
                    continue
                job_url = job.get("hostedUrl") or job.get("applyUrl", "")
                job_id = job.get("id", "")
                results.append(Listing(
                    title=title,
                    company=company,
                    location=location or "Austin, TX",
                    url=job_url,
                    source="Lever",
                    date_posted=datetime.now(),
                    job_id=str(job_id),
                ))
            if results:
                break  # found results with this commitment type
        return results

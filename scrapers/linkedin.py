import re
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing

_DATE_FILTERS = {7: "r604800", 30: "r2592000"}


class LinkedInScraper(BaseScraper):
    SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def search(self, keyword: str) -> list[Listing]:
        results = []
        max_days = self.config["search"]["max_days_old"]
        f_TPR = _DATE_FILTERS.get(30 if max_days >= 30 else 7, "r2592000")

        for start in range(0, 75, 25):
            params = {
                "keywords": keyword,
                "location": self.location,
                "f_JT": "I",
                "f_TPR": f_TPR,
                "start": start,
                "sortBy": "DD",
            }
            url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"
            resp = self._get(url)
            if not resp or not resp.text.strip():
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("li")
            if not cards:
                break

            for card in cards:
                listing = self._parse_card(card)
                if listing:
                    results.append(listing)

        return results

    def _parse_card(self, card):
        try:
            title_el = card.select_one(".base-search-card__title")
            company_el = card.select_one(".base-search-card__subtitle")
            location_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a.base-card__full-link") or card.select_one("a[href*='/jobs/view/']")
            date_el = card.select_one("time")

            if not title_el or not link_el:
                return None

            title = title_el.get_text(strip=True)
            url = link_el.get("href", "").split("?")[0]
            job_id_match = re.search(r"/jobs/view/(\d+)", url)

            date_posted = None
            if date_el:
                try:
                    date_posted = datetime.fromisoformat(date_el.get("datetime", ""))
                except ValueError:
                    pass

            return Listing(
                title=title,
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                location=location_el.get_text(strip=True) if location_el else self.location,
                url=url,
                source="LinkedIn",
                date_posted=date_posted,
                job_id=job_id_match.group(1) if job_id_match else "",
            )
        except Exception:
            return None

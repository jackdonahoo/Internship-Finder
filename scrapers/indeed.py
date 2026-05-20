import re
import urllib.parse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from .base import BaseScraper, Listing


class IndeedScraper(BaseScraper):
    BASE_URL = "https://www.indeed.com/jobs"

    def search(self, keyword: str) -> list[Listing]:
        results = []
        start = 0

        for _ in range(3):
            params = {
                "q": keyword,
                "l": self.location,
                "fromage": str(self.config["search"]["max_days_old"]),
                "start": start,
                "sort": "date",
            }
            url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
            resp = self._get(url)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select("div.job_seen_beacon")
            if not cards:
                break

            for card in cards:
                listing = self._parse_card(card)
                if listing:
                    results.append(listing)

            start += 15

        return results

    def _parse_card(self, card):
        try:
            title_el = card.select_one("h2.jobTitle span[title]") or card.select_one("h2.jobTitle")
            company_el = card.select_one("[data-testid='company-name']") or card.select_one(".companyName")
            location_el = card.select_one("[data-testid='text-location']") or card.select_one(".companyLocation")
            link_el = card.select_one("h2.jobTitle a") or card.select_one("a.jcs-JobTitle")
            date_el = card.select_one("[data-testid='myJobsStateDate']") or card.select_one(".date")
            salary_el = card.select_one(".estimated-salary") or card.select_one(".salary-snippet")

            if not title_el or not link_el:
                return None

            title = title_el.get_text(strip=True)
            if "intern" not in title.lower():
                return None

            href = link_el.get("href", "")
            url = f"https://www.indeed.com{href}" if href.startswith("/") else href
            job_id_match = re.search(r"jk=([a-f0-9]+)", url)

            return Listing(
                title=title,
                company=company_el.get_text(strip=True) if company_el else "Unknown",
                location=location_el.get_text(strip=True) if location_el else self.location,
                url=url,
                source="Indeed",
                date_posted=self._parse_date(date_el.get_text(strip=True) if date_el else ""),
                salary=salary_el.get_text(strip=True) if salary_el else "",
                job_id=job_id_match.group(1) if job_id_match else "",
            )
        except Exception:
            return None

    def _parse_date(self, text: str):
        text = text.lower()
        today = datetime.now()
        if "today" in text or "just posted" in text:
            return today
        if "yesterday" in text:
            return today - timedelta(days=1)
        match = re.search(r"(\d+)\s*day", text)
        if match:
            return today - timedelta(days=int(match.group(1)))
        return None

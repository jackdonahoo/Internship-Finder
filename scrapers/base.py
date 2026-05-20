import random
import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from fake_useragent import UserAgent


@dataclass
class Listing:
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    date_posted: Optional[datetime] = None
    job_id: str = ""
    salary: str = ""
    remote: bool = False
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "source": self.source,
            "description": self.description[:500] if self.description else "",
            "date_posted": self.date_posted.strftime("%Y-%m-%d") if self.date_posted else "",
            "job_id": self.job_id,
            "salary": self.salary,
            "remote": self.remote,
            "tags": ", ".join(self.tags),
        }


class BaseScraper(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.location = config["search"]["location"]
        self.keywords = config["search"]["keywords"]
        self.delay_min = config["browser"]["request_delay_min"]
        self.delay_max = config["browser"]["request_delay_max"]
        self._ua = UserAgent()
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "User-Agent": self._ua.random,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        return session

    def _sleep(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    def _get(self, url: str, **kwargs) -> Optional[requests.Response]:
        try:
            self._sleep()
            resp = self._session.get(url, timeout=15, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"[{self.__class__.__name__}] Request failed: {e}")
            return None

    @abstractmethod
    def search(self, keyword: str) -> list[Listing]:
        """Return a list of Listing objects for the given keyword."""

    def search_all(self) -> list[Listing]:
        seen_urls: set[str] = set()
        results: list[Listing] = []
        for kw in self.keywords:
            for listing in self.search(kw):
                if listing.url not in seen_urls:
                    seen_urls.add(listing.url)
                    results.append(listing)
        return results

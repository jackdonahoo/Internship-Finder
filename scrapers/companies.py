from datetime import datetime
from bs4 import BeautifulSoup
from .base import BaseScraper, Listing

_SCRAPERS = {}


def _register(name):
    def decorator(fn):
        _SCRAPERS[name] = fn
        return fn
    return decorator


class CompanyScraper(BaseScraper):
    def search(self, keyword):
        return []

    def scrape_all_companies(self) -> list[Listing]:
        results = []
        headless = self.config["browser"]["headless"]
        slow_mo = self.config["browser"]["slow_mo"]

        for company in self.config.get("target_companies", []):
            name = company["name"]
            url = company.get("careers_url", "")
            if not url:
                continue
            fn = _SCRAPERS.get(name)
            try:
                listings = fn(self, name, url, headless, slow_mo) if fn else self._generic_scrape(name, url)
                results.extend(listings)
                print(f"[Companies] {name}: {len(listings)} listing(s)")
            except Exception as e:
                print(f"[Companies] {name}: failed -- {e}")

        return results

    def _generic_scrape(self, company, url):
        resp = self._get(url)
        if not resp:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        seen = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = a["href"]
            if "intern" in text and href not in seen:
                seen.add(href)
                full_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                results.append(Listing(
                    title=a.get_text(strip=True),
                    company=company,
                    location="Austin, TX",
                    url=full_url,
                    source="Company Page",
                    date_posted=datetime.now(),
                ))
        return results[:10]


@_register("Dell Technologies")
def _scrape_dell(scraper, name, url, headless, slow_mo):
    resp = scraper._get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for item in soup.select("li.search-result, article.job-result, .job-listing"):
        title_el = item.select_one("h2, h3, .job-title, [class*='title']")
        link_el = item.select_one("a[href]")
        if not title_el or not link_el:
            continue
        href = link_el["href"]
        results.append(Listing(
            title=title_el.get_text(strip=True),
            company=name,
            location="Austin, TX",
            url=href if href.startswith("http") else f"https://jobs.dell.com{href}",
            source="Company Page",
            date_posted=datetime.now(),
        ))
    return results


@_register("Indeed HQ")
def _scrape_indeed_hq(scraper, name, url, headless, slow_mo):
    resp = scraper._get(url)
    if not resp:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for item in soup.select("[class*='job'], [class*='listing'], li"):
        title_el = item.select_one("h2, h3, [class*='title']")
        link_el = item.select_one("a[href]")
        if not title_el:
            continue
        text = title_el.get_text(strip=True)
        if "intern" not in text.lower():
            continue
        href = link_el["href"] if link_el else url
        results.append(Listing(
            title=text,
            company=name,
            location="Austin, TX",
            url=href if href.startswith("http") else f"https://careers.indeed.com{href}",
            source="Company Page",
            date_posted=datetime.now(),
        ))
    return results[:10]

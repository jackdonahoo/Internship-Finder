from datetime import datetime
from .base import BaseScraper, Listing

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class HandshakeScraper(BaseScraper):
    LOGIN_URL = "https://app.joinhandshake.com/login"

    def search(self, keyword: str) -> list[Listing]:
        if not PLAYWRIGHT_AVAILABLE:
            print("[Handshake] Playwright not installed.")
            return []

        creds = self.config.get("handshake", {})
        if not creds.get("email") or not creds.get("password"):
            print("[Handshake] No credentials configured in config.yaml.")
            return []

        headless = self.config["browser"]["headless"]
        slow_mo = self.config["browser"]["slow_mo"]
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
            page = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            ).new_page()
            try:
                self._login(page, creds["email"], creds["password"])
                results = self._scrape_search(page, keyword)
            except Exception as e:
                print(f"[Handshake] Error: {e}")
            finally:
                browser.close()

        return results

    def _login(self, page, email, password):
        page.goto(self.LOGIN_URL, timeout=30000)
        page.wait_for_selector("input[type='email']", timeout=15000)
        page.fill("input[type='email']", email)
        page.click("button[type='submit']")
        page.wait_for_selector("input[type='password']", timeout=10000)
        page.fill("input[type='password']", password)
        page.click("button[type='submit']")
        page.wait_for_url("**/stu/**", timeout=20000)

    def _scrape_search(self, page, keyword):
        import urllib.parse
        params = urllib.parse.urlencode({
            "query": keyword,
            "location": "Austin, TX",
            "employment_type_names[]": "Internship",
            "sort_direction": "desc",
            "sort_column": "created_at",
        })
        page.goto(f"https://app.joinhandshake.com/stu/postings?{params}", timeout=30000)
        try:
            page.wait_for_selector("[data-hook='posting-card']", timeout=15000)
        except PWTimeout:
            return []

        results = []
        for card in page.query_selector_all("[data-hook='posting-card']")[:20]:
            try:
                title = card.query_selector("h3") or card.query_selector("[class*='title']")
                company = card.query_selector("[class*='employer']") or card.query_selector("[class*='company']")
                link = card.query_selector("a[href*='/postings/']")
                if not title or not link:
                    continue
                href = link.get_attribute("href") or ""
                url = f"https://app.joinhandshake.com{href}" if href.startswith("/") else href
                results.append(Listing(
                    title=title.inner_text().strip(),
                    company=company.inner_text().strip() if company else "Unknown",
                    location="Austin, TX",
                    url=url,
                    source="Handshake",
                    date_posted=datetime.now(),
                ))
            except Exception:
                continue
        return results

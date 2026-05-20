from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

ATS_PATTERNS = {
    "workday": "myworkdayjobs.com",
    "greenhouse": "greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "ashbyhq.com",
}


class AutoFiller:
    def __init__(self, config: dict):
        self.profile = config.get("profile", {})
        self.headless = config["browser"]["headless"]
        self.slow_mo = config["browser"]["slow_mo"]

    def fill(self, url: str) -> bool:
        if not PLAYWRIGHT_AVAILABLE:
            print("[AutoFill] Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False

        ats = next((k for k, v in ATS_PATTERNS.items() if v in url), None)
        print(f"[AutoFill] Detected ATS: {ats or 'generic'}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            page = browser.new_page()
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=20000)
                handlers = {
                    "workday": self._fill_workday,
                    "greenhouse": self._fill_greenhouse,
                    "lever": self._fill_lever,
                    "ashby": self._fill_ashby,
                }
                success = handlers.get(ats, self._fill_generic)(page)
                if success:
                    print("[AutoFill] Form filled. Review carefully before submitting!")
                    input("[AutoFill] Press Enter after reviewing to close the browser...")
                return success
            except Exception as e:
                print(f"[AutoFill] Error: {e}")
                return False
            finally:
                browser.close()

    def _fill_workday(self, page: "Page") -> bool:
        p = self.profile
        try:
            btn = page.locator("a[data-automation-id='applyButton'], button[aria-label*='Apply']").first
            if btn.is_visible():
                btn.click()
                page.wait_for_load_state("networkidle", timeout=15000)
            self._safe_fill(page, "[data-automation-id='legalNameSection_firstName']", p.get("first_name", ""))
            self._safe_fill(page, "[data-automation-id='legalNameSection_lastName']", p.get("last_name", ""))
            self._safe_fill(page, "input[type='email']", p.get("email", ""))
            self._safe_fill(page, "input[type='tel']", p.get("phone", ""))
            resume = p.get("resume_path", "")
            if resume and Path(resume).exists():
                fi = page.locator("input[type='file']").first
                if fi.is_visible():
                    fi.set_input_files(resume)
            return True
        except Exception as e:
            print(f"[AutoFill/Workday] {e}")
            return False

    def _fill_greenhouse(self, page: "Page") -> bool:
        p = self.profile
        try:
            self._safe_fill(page, "#first_name", p.get("first_name", ""))
            self._safe_fill(page, "#last_name", p.get("last_name", ""))
            self._safe_fill(page, "#email", p.get("email", ""))
            self._safe_fill(page, "#phone", p.get("phone", ""))
            if p.get("linkedin_url"):
                self._safe_fill(page, "input[name*='linkedin'], input[id*='linkedin']", p["linkedin_url"])
            resume = p.get("resume_path", "")
            if resume and Path(resume).exists():
                fi = page.locator("#resume, input[type='file'][name*='resume']").first
                if fi.count() > 0:
                    fi.set_input_files(resume)
            return True
        except Exception as e:
            print(f"[AutoFill/Greenhouse] {e}")
            return False

    def _fill_lever(self, page: "Page") -> bool:
        p = self.profile
        try:
            self._safe_fill(page, "input[name='name']", f"{p.get('first_name','')} {p.get('last_name','')}".strip())
            self._safe_fill(page, "input[name='email']", p.get("email", ""))
            self._safe_fill(page, "input[name='phone']", p.get("phone", ""))
            self._safe_fill(page, "input[name='urls[LinkedIn]']", p.get("linkedin_url", ""))
            self._safe_fill(page, "input[name='urls[GitHub]']", p.get("github_url", ""))
            self._safe_fill(page, "input[name='urls[Portfolio]']", p.get("portfolio_url", ""))
            resume = p.get("resume_path", "")
            if resume and Path(resume).exists():
                fi = page.locator("input[type='file']").first
                if fi.count() > 0:
                    fi.set_input_files(resume)
            return True
        except Exception as e:
            print(f"[AutoFill/Lever] {e}")
            return False

    def _fill_ashby(self, page: "Page") -> bool:
        p = self.profile
        try:
            self._safe_fill(page, "input[name*='firstName'], input[placeholder*='First']", p.get("first_name", ""))
            self._safe_fill(page, "input[name*='lastName'], input[placeholder*='Last']", p.get("last_name", ""))
            self._safe_fill(page, "input[type='email']", p.get("email", ""))
            self._safe_fill(page, "input[type='tel']", p.get("phone", ""))
            return True
        except Exception as e:
            print(f"[AutoFill/Ashby] {e}")
            return False

    def _fill_generic(self, page: "Page") -> bool:
        p = self.profile
        filled = 0
        field_map = {
            "first": p.get("first_name", ""), "fname": p.get("first_name", ""),
            "last": p.get("last_name", ""), "lname": p.get("last_name", ""),
            "email": p.get("email", ""), "phone": p.get("phone", ""),
            "linkedin": p.get("linkedin_url", ""), "github": p.get("github_url", ""),
            "portfolio": p.get("portfolio_url", ""), "university": p.get("university", ""),
            "school": p.get("university", ""), "major": p.get("major", ""),
            "gpa": p.get("gpa", ""), "graduation": p.get("graduation_year", ""),
        }
        for inp in page.locator("input[type='text'], input[type='email'], input[type='tel']").all():
            try:
                attrs = " ".join(filter(None, [
                    inp.get_attribute("name") or "", inp.get_attribute("id") or "",
                    inp.get_attribute("placeholder") or "", inp.get_attribute("aria-label") or "",
                ])).lower()
                for key, value in field_map.items():
                    if value and key in attrs:
                        inp.fill(value)
                        filled += 1
                        break
            except Exception:
                continue
        resume = p.get("resume_path", "")
        if resume and Path(resume).exists():
            try:
                fi = page.locator("input[type='file']").first
                if fi.count() > 0:
                    fi.set_input_files(resume)
                    filled += 1
            except Exception:
                pass
        return filled > 0

    def _safe_fill(self, page: "Page", selector: str, value: str):
        if not value:
            return
        try:
            el = page.locator(selector).first
            if el.count() > 0 and el.is_visible():
                el.fill(value)
        except Exception:
            pass

from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

ATS_PATTERNS = {
    "workday": "myworkdayjobs.com",
    "greenhouse": "greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "ashbyhq.com",
}

SUBMIT_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Submit')",
    "button:has-text('Submit Application')",
    "button:has-text('Apply Now')",
    "button:has-text('Send Application')",
    "button:has-text('Complete Application')",
    "[data-automation-id='bottom-navigation-next-button']",
]


class AutoFiller:
    def __init__(self, config: dict):
        self.profile = config.get("profile", {})
        self.headless = config["browser"]["headless"]
        self.slow_mo = config["browser"]["slow_mo"]

    def fill(self, url: str, auto_submit: bool = False) -> bool:
        if not PLAYWRIGHT_AVAILABLE:
            print("[AutoFill] Playwright not installed.")
            return False

        from session_manager import load_session

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="chrome", headless=self.headless, slow_mo=self.slow_mo)
            except Exception:
                browser = p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)

            ctx_kwargs = {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            if "linkedin.com" in url:
                session_path = load_session("linkedin")
                if session_path:
                    ctx_kwargs["storage_state"] = session_path

            ctx = browser.new_context(**ctx_kwargs)
            page = ctx.new_page()
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=20000)

                # Follow through LinkedIn job pages to the real application
                if "linkedin.com/jobs" in url:
                    url = self._navigate_linkedin(page, url)
                    if not url:
                        print("[AutoFill] Could not reach application form from LinkedIn.")
                        return False

                ats = next((k for k, v in ATS_PATTERNS.items() if v in page.url), None)
                print(f"[AutoFill] ATS: {ats or 'generic'} | URL: {page.url[:80]}")

                handlers = {
                    "workday": self._fill_workday,
                    "greenhouse": self._fill_greenhouse,
                    "lever": self._fill_lever,
                    "ashby": self._fill_ashby,
                }
                success = handlers.get(ats, self._fill_generic)(page)

                if success:
                    if auto_submit:
                        submitted = self._try_submit(page)
                        if submitted:
                            print("[AutoFill] Form submitted.")
                        else:
                            print("[AutoFill] Could not auto-submit — form may need manual review.")
                            input("[AutoFill] Press Enter to close browser...")
                    else:
                        print("[AutoFill] Form filled. Review and submit manually.")
                        input("[AutoFill] Press Enter after submitting to close browser...")
                else:
                    print("[AutoFill] Could not fill form — may require manual interaction.")
                    if not auto_submit:
                        input("[AutoFill] Press Enter to close browser...")

                return success
            except Exception as e:
                print(f"[AutoFill] Error: {e}")
                return False
            finally:
                browser.close()

    def _navigate_linkedin(self, page: "Page", original_url: str) -> str:
        """Click Apply on a LinkedIn job page and follow to the real application form."""
        try:
            # Try "Easy Apply" (LinkedIn's own form — needs login, skip)
            # Try external "Apply" button that opens company ATS
            apply_btn = page.locator(
                "a.apply-button, a[data-tracking-control-name='public_jobs_apply-link-offsite_sign-up-modal'], "
                "button.apply-button, a[href*='apply'], .jobs-apply-button"
            ).first

            if apply_btn.count() == 0:
                # Try clicking "Apply" text on the page
                apply_btn = page.get_by_role("link", name="Apply").first

            if apply_btn.count() > 0 and apply_btn.is_visible():
                with page.expect_popup(timeout=10000) as popup_info:
                    apply_btn.click()
                popup = popup_info.value
                popup.wait_for_load_state("networkidle", timeout=20000)
                # Bring popup into main page context
                page.close()
                return popup.url
            else:
                print("[AutoFill] No external Apply button found on LinkedIn page.")
                return ""
        except PWTimeout:
            # No popup — might have navigated in same tab
            if page.url != original_url:
                return page.url
            return ""
        except Exception as e:
            print(f"[AutoFill/LinkedIn] {e}")
            return ""

    def _try_submit(self, page: "Page") -> bool:
        for sel in SUBMIT_SELECTORS:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                    btn.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    return True
            except Exception:
                continue
        return False

    def _fill_workday(self, page: "Page") -> bool:
        p = self.profile
        try:
            btn = page.locator("a[data-automation-id='applyButton'], button[aria-label*='Apply']").first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                page.wait_for_load_state("networkidle", timeout=15000)
            self._safe_fill(page, "[data-automation-id='legalNameSection_firstName']", p.get("first_name", ""))
            self._safe_fill(page, "[data-automation-id='legalNameSection_lastName']", p.get("last_name", ""))
            self._safe_fill(page, "input[type='email']", p.get("email", ""))
            self._safe_fill(page, "input[type='tel']", p.get("phone", ""))
            resume = p.get("resume_path", "")
            if resume and Path(resume).exists():
                fi = page.locator("input[type='file']").first
                if fi.count() > 0 and fi.is_visible():
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

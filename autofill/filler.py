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

        with sync_playwright() as p:
            ctx = self._launch_chrome_context(p)
            page = ctx.new_page()
            try:
                original_url = url
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=20000)
                page.wait_for_timeout(3000)  # let JS render after DOM load

                # Follow through LinkedIn job pages to the real application
                if "linkedin.com/jobs" in url:
                    url = self._navigate_linkedin(page, url)
                    if not url:
                        print("[AutoFill] Could not reach application form from LinkedIn.")
                        return False

                # After LinkedIn navigation the active page may be a popup
                active_page = page
                for p_ctx in ctx.pages:
                    if p_ctx.url != original_url and p_ctx != page:
                        active_page = p_ctx
                        break

                ats = next((k for k, v in ATS_PATTERNS.items() if v in active_page.url), None)
                is_easy_apply = "linkedin.com" in active_page.url
                print(f"[AutoFill] ATS: {'linkedin-easy-apply' if is_easy_apply else (ats or 'generic')} | URL: {active_page.url[:80]}")

                handlers = {
                    "workday": self._fill_workday,
                    "greenhouse": self._fill_greenhouse,
                    "lever": self._fill_lever,
                    "ashby": self._fill_ashby,
                }
                if is_easy_apply:
                    success = self._fill_linkedin_easy_apply(active_page)
                else:
                    success = handlers.get(ats, self._fill_generic)(active_page)

                if success:
                    if auto_submit:
                        submitted = self._try_submit(active_page)
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
                ctx.close()

    def _launch_chrome_context(self, p):
        """Launch Chrome with the user's real profile so Google/LinkedIn sessions work."""
        import os, shutil, tempfile
        chrome_profile = os.path.expanduser("~/Library/Application Support/Google/Chrome")
        if os.path.isdir(chrome_profile):
            # Copy Default profile to a temp dir so we don't conflict with a running Chrome
            tmp = tempfile.mkdtemp(prefix="pw_chrome_")
            default_src = os.path.join(chrome_profile, "Default")
            default_dst = os.path.join(tmp, "Default")
            if os.path.isdir(default_src):
                shutil.copytree(default_src, default_dst, ignore=shutil.ignore_patterns(
                    "Cache", "Code Cache", "GPUCache", "ShaderCache",
                    "Service Worker", "CacheStorage", "IndexedDB",
                ))
            try:
                return p.chromium.launch_persistent_context(
                    user_data_dir=tmp,
                    channel="chrome",
                    headless=self.headless,
                    slow_mo=self.slow_mo,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except Exception as e:
                print(f"[AutoFill] Chrome profile launch failed ({e}), falling back.")

        # Fallback: plain Chromium
        browser = p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
        return browser.new_context()

    def _navigate_linkedin(self, page: "Page", original_url: str) -> str:
        """Click Apply on a LinkedIn job page and follow to the real application form."""
        try:
            # Logged-in LinkedIn job page selectors (tried in order)
            apply_selectors = [
                # External apply (opens company ATS)
                "a.jobs-apply-button",
                "a[data-job-id][href*='apply']",
                "a[href*='linkedin.com/job-apply']",
                # Easy Apply button (LinkedIn's own flow)
                "button.jobs-apply-button",
                ".jobs-apply-button",
                # Fallback: any visible Apply/Easy Apply button
                "button:has-text('Easy Apply')",
                "button:has-text('Apply')",
                "a:has-text('Apply')",
            ]

            apply_btn = None
            for sel in apply_selectors:
                candidate = page.locator(sel).first
                try:
                    if candidate.count() > 0 and candidate.is_visible(timeout=1000):
                        apply_btn = candidate
                        print(f"[AutoFill/LinkedIn] Found apply button via: {sel}")
                        break
                except Exception:
                    continue

            if not apply_btn:
                print("[AutoFill] No external Apply button found on LinkedIn page.")
                return ""

            # Check if it opens a popup (external ATS) or navigates in-page (Easy Apply)
            try:
                with page.expect_popup(timeout=8000) as popup_info:
                    apply_btn.click()
                popup = popup_info.value
                popup.wait_for_load_state("domcontentloaded", timeout=20000)
                popup.wait_for_timeout(2000)
                return popup.url
            except PWTimeout:
                # No popup — either navigated in-tab or opened Easy Apply modal
                page.wait_for_timeout(2000)
                if page.url != original_url:
                    return page.url
                # Easy Apply modal opened in-page — treat current page as form
                if page.locator(".jobs-easy-apply-modal, [data-test-modal]").count() > 0:
                    print("[AutoFill/LinkedIn] Easy Apply modal detected — filling inline.")
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

    def _fill_linkedin_easy_apply(self, page: "Page") -> bool:
        """Fill LinkedIn Easy Apply modal — handles contact info step and resume upload."""
        p = self.profile
        try:
            modal = page.locator(".jobs-easy-apply-modal, [data-test-modal], [role='dialog']").first
            if modal.count() == 0:
                return self._fill_generic(page)

            # Phone field (LinkedIn often pre-fills name/email from your profile)
            self._safe_fill(page, "input[id*='phoneNumber'], input[name*='phone']", p.get("phone", ""))

            # Resume upload
            resume = p.get("resume_path", "")
            if resume and Path(resume).exists():
                upload = page.locator("input[type='file']").first
                if upload.count() > 0:
                    upload.set_input_files(resume)
                    page.wait_for_timeout(1500)

            return True
        except Exception as e:
            print(f"[AutoFill/LinkedIn-EasyApply] {e}")
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

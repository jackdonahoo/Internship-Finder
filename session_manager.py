#!/usr/bin/env python3
"""
Save and reuse browser sessions so Google/SSO login only needs to happen once.

Usage:
    python session_manager.py save linkedin   # opens real Chrome, you log in, session saved
    python session_manager.py save handshake
    python session_manager.py status          # shows which sessions are saved
    python session_manager.py clear linkedin  # deletes a saved session
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

SESSIONS_DIR = Path("private/sessions")

SITES = {
    "linkedin": {
        "url": "https://www.linkedin.com/login",
        "wait_for": "**/feed**",
        "label": "LinkedIn",
    },
    "handshake": {
        "url": "https://app.joinhandshake.com/login",
        "wait_for": "**/stu/**",
        "label": "Handshake",
    },
}


def get_session_path(site: str) -> Path:
    return SESSIONS_DIR / f"{site}_session.json"


def save_session(site: str):
    if site not in SITES:
        print(f"Unknown site '{site}'. Choices: {', '.join(SITES)}")
        sys.exit(1)

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = SITES[site]
    session_path = get_session_path(site)

    print(f"\n=== Saving {cfg['label']} session ===")
    print("A browser window will open. Log in normally (Google Sign-In works fine).")
    print("Once you're logged in and see your home/dashboard page, come back here and press Enter.\n")

    with sync_playwright() as p:
        # Use installed Chrome so Google OAuth works
        try:
            browser = p.chromium.launch(channel="chrome", headless=False, slow_mo=30)
        except Exception:
            # Fall back to Playwright's Chromium if Chrome isn't installed
            browser = p.chromium.launch(headless=False, slow_mo=30)

        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(cfg["url"], timeout=30000)

        input(f"Log in to {cfg['label']} in the browser, then press Enter here to save your session...")

        ctx.storage_state(path=str(session_path))
        browser.close()

    print(f"Session saved to {session_path}")


def show_status():
    print("\nSaved sessions:")
    for site, cfg in SITES.items():
        path = get_session_path(site)
        if path.exists():
            data = json.loads(path.read_text())
            cookies = len(data.get("cookies", []))
            print(f"  {cfg['label']:12} ✓  ({cookies} cookies) — {path}")
        else:
            print(f"  {cfg['label']:12} ✗  not saved")


def clear_session(site: str):
    path = get_session_path(site)
    if path.exists():
        path.unlink()
        print(f"Cleared {site} session.")
    else:
        print(f"No saved session for {site}.")


def load_session(site: str):
    """Returns path string if session exists, else None."""
    path = get_session_path(site)
    return str(path) if path.exists() else None


if __name__ == "__main__":
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Manage browser sessions for automation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_save = sub.add_parser("save", help="Save a login session")
    p_save.add_argument("site", choices=list(SITES))

    p_clear = sub.add_parser("clear", help="Delete a saved session")
    p_clear.add_argument("site", choices=list(SITES))

    sub.add_parser("status", help="Show which sessions are saved")

    args = parser.parse_args()

    if args.cmd == "save":
        save_session(args.site)
    elif args.cmd == "clear":
        clear_session(args.site)
    elif args.cmd == "status":
        show_status()

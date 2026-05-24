#!/usr/bin/env python3
"""
Internship Finder -- Austin, TX
Searches LinkedIn, Indeed, Handshake, and company career pages for
CS / CE / AI internships and tracks your applications.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table
from rich import box
from rich.prompt import Prompt, Confirm

console = Console()

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        os.environ.setdefault(key, value)


def _expand_env_values(value):
    if isinstance(value, dict):
        return {key: _expand_env_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_values(item) for item in value]
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)
    return value


def load_config(path: str = "config.yaml") -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        console.print(f"[red]Config file not found: {path}[/red]")
        sys.exit(1)
    _load_dotenv(cfg_path.with_name(".env"))
    with open(cfg_path) as f:
        config = yaml.safe_load(f) or {}
    return _expand_env_values(config)


def cmd_search(args, config: dict):
    """Scrape all enabled sources and store new listings."""
    from scrapers.indeed import IndeedScraper
    from scrapers.linkedin import LinkedInScraper
    from scrapers.handshake import HandshakeScraper
    from scrapers.companies import CompanyScraper
    from scrapers.ats import GreenhouseScraper, LeverScraper
    from tracker.database import Database
    from notifier.email_digest import send_digest

    db = Database()

    if config.get("indeed", {}).get("enabled", True):
        console.print("[cyan]Scanning Indeed...[/cyan]")
        scraper = IndeedScraper(config)
        listings = scraper.search_all()
        new_count = _upsert_listings(db, listings, config)
        console.print(f"  Indeed: {len(listings)} found, [green]{new_count} new[/green]")

    if config.get("linkedin", {}).get("enabled", True):
        console.print("[cyan]Scanning LinkedIn...[/cyan]")
        scraper = LinkedInScraper(config)
        listings = scraper.search_all()
        new_count = _upsert_listings(db, listings, config)
        console.print(f"  LinkedIn: {len(listings)} found, [green]{new_count} new[/green]")

    if config.get("handshake", {}).get("enabled", False):
        console.print("[cyan]Scanning Handshake...[/cyan]")
        scraper = HandshakeScraper(config)
        listings = scraper.search_all()
        new_count = _upsert_listings(db, listings, config)
        console.print(f"  Handshake: {len(listings)} found, [green]{new_count} new[/green]")

    console.print("[cyan]Scanning company career pages...[/cyan]")
    scraper = CompanyScraper(config)
    listings = scraper.scrape_all_companies()
    new_count = _upsert_listings(db, listings, config)
    console.print(f"  Company pages: {len(listings)} found, [green]{new_count} new[/green]")

    if config.get("greenhouse_boards"):
        console.print("[cyan]Scanning Greenhouse boards...[/cyan]")
        gh = GreenhouseScraper(config)
        listings = gh.search_all_boards()
        new_count = _upsert_listings(db, listings, config)
        console.print(f"  Greenhouse: {len(listings)} found, [green]{new_count} new[/green]")

    if config.get("lever_boards"):
        console.print("[cyan]Scanning Lever boards...[/cyan]")
        lv = LeverScraper(config)
        listings = lv.search_all_boards()
        new_count = _upsert_listings(db, listings, config)
        console.print(f"  Lever: {len(listings)} found, [green]{new_count} new[/green]")

    recent = db.get_new_since(datetime.now() - timedelta(hours=1))
    if config.get("email", {}).get("enabled") and recent:
        send_digest(config, [dict(r) for r in recent])

    console.print(f"\n[bold green]Done.[/bold green] Run [yellow]python main.py list[/yellow] to review listings.")
    db.close()


def cmd_list(args, config: dict):
    """Display stored listings in a table."""
    from tracker.database import Database

    db = Database()
    status_filter = getattr(args, "status", None)
    rows = db.get_all(status=status_filter)
    db.close()

    if not rows:
        console.print("[yellow]No listings found. Run [bold]python main.py search[/bold] first.[/yellow]")
        return

    table = Table(
        title=f"Internship Listings{' -- ' + status_filter if status_filter else ''}",
        box=box.ROUNDED,
        show_lines=False,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", min_width=25)
    table.add_column("Company", min_width=18)
    table.add_column("Source", width=12)
    table.add_column("Posted", width=10)
    table.add_column("Status", width=14)

    status_colors = {
        "new": "white",
        "reviewed": "cyan",
        "applied": "blue",
        "interview_scheduled": "magenta",
        "interviewed": "purple",
        "offer": "green",
        "rejected": "red",
        "withdrawn": "dim",
    }

    for i, row in enumerate(rows, 1):
        color = status_colors.get(row["status"], "white")
        table.add_row(
            str(row["id"]),
            row["title"],
            row["company"],
            row["source"],
            row["date_posted"] or "",
            f"[{color}]{row['status']}[/{color}]",
        )

    console.print(table)
    console.print(f"\nTotal: {len(rows)} listing(s)")


def cmd_stats(args, config: dict):
    """Show application pipeline stats."""
    from tracker.database import Database

    db = Database()
    stats = db.stats()
    db.close()

    table = Table(title="Application Pipeline", box=box.SIMPLE_HEAVY)
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right", style="cyan")

    order = ["new", "reviewed", "applied", "interview_scheduled", "interviewed", "offer", "rejected", "withdrawn"]
    total = sum(stats.values())
    for s in order:
        cnt = stats.get(s, 0)
        if cnt > 0:
            table.add_row(s.replace("_", " ").title(), str(cnt))

    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")
    console.print(table)


def cmd_update(args, config: dict):
    """Update the status of a listing."""
    from tracker.database import Database, STATUSES

    db = Database()
    listing_id = args.id

    row = db._conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row:
        console.print(f"[red]Listing #{listing_id} not found.[/red]")
        db.close()
        return

    console.print(f"\n[bold]{row['title']}[/bold] @ {row['company']}")
    console.print(f"URL: [link={row['url']}]{row['url']}[/link]")
    console.print(f"Current status: [yellow]{row['status']}[/yellow]")
    console.print(f"\nAvailable statuses: {', '.join(STATUSES)}")

    new_status = Prompt.ask("New status", choices=STATUSES, default=row["status"])
    notes = Prompt.ask("Notes (optional)", default=row["notes"] or "")

    if db.update_status(listing_id, new_status, notes):
        console.print(f"[green]Updated #{listing_id} to '{new_status}'[/green]")
    else:
        console.print("[red]Update failed.[/red]")

    db.close()


def cmd_export(args, config: dict):
    """Export all listings to CSV."""
    from tracker.database import Database
    from exporter.csv_export import export_to_csv

    db = Database()
    rows = db.get_all()
    db.close()

    if not rows:
        console.print("[yellow]No listings to export.[/yellow]")
        return

    out_path = export_to_csv(rows)
    console.print(f"[green]Exported {len(rows)} listing(s) to:[/green] {out_path}")


def cmd_apply(args, config: dict):
    """Open a listing's application form and auto-fill your profile."""
    from tracker.database import Database
    from autofill.filler import AutoFiller

    db = Database()
    listing_id = args.id
    row = db._conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()

    if not row:
        console.print(f"[red]Listing #{listing_id} not found.[/red]")
        db.close()
        return

    console.print(f"\n[bold]Applying to:[/bold] {row['title']} @ {row['company']}")
    console.print(f"URL: {row['url']}\n")

    if not Confirm.ask("Open browser and auto-fill?"):
        db.close()
        return

    filler = AutoFiller(config)
    success = filler.fill(row["url"])

    if success and Confirm.ask("Mark as 'applied' in the tracker?"):
        notes = Prompt.ask("Any notes?", default="")
        db.update_status(listing_id, "applied", notes)
        console.print(f"[green]#{listing_id} marked as applied.[/green]")

    db.close()


def cmd_batch_apply(args, config: dict):
    """Open all matching listings in Chrome and track them once you confirm."""
    import subprocess
    import time
    from tracker.database import Database

    db = Database()
    ids = args.ids

    rows = []
    for listing_id in ids:
        row = db._conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if not row:
            console.print(f"[red]#{listing_id} not found, skipping.[/red]")
            continue
        if row["status"] == "applied":
            console.print(f"[dim]#{listing_id} already applied, skipping.[/dim]")
            continue
        rows.append(row)

    if not rows:
        console.print("[yellow]Nothing to apply to.[/yellow]")
        db.close()
        return

    console.print(f"\n[bold cyan]Opening {len(rows)} job(s) in Chrome...[/bold cyan]\n")
    for row in rows:
        console.print(f"  #{row['id']} [bold]{row['title']}[/bold] @ {row['company']}")
        console.print(f"       {row['url']}")
        subprocess.run(["open", row["url"]], check=False)
        time.sleep(0.8)  # stagger tab opens slightly

    console.print(f"\n[green]All {len(rows)} tabs opened.[/green]")
    console.print("Apply to each one in Chrome (Easy Apply or external form), then come back here.\n")

    applied = []
    for row in rows:
        answer = Confirm.ask(f"Did you apply to [bold]{row['title']}[/bold] @ {row['company']}?", default=True)
        if answer:
            db.update_status(row["id"], "applied", "batch apply")
            applied.append(row)

    db.close()

    console.print(f"\n[bold green]--- Applications Submitted ---[/bold green]")
    if applied:
        for a in applied:
            console.print(f"  ✓ #{a['id']} {a['title']} @ {a['company']}")
    console.print(f"\n[bold]{len(applied)}/{len(rows)} tracked as applied.[/bold]")


def cmd_daemon(args, config: dict):
    """Run as a background daemon: scan on schedule, send daily digests."""
    import schedule
    import time

    digest_time = config.get("email", {}).get("digest_time", "08:00")

    def run_search():
        console.print(f"\n[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim] Running scheduled scan...")
        cmd_search(args, config)

    schedule.every(6).hours.do(run_search)
    schedule.every().day.at(digest_time).do(run_search)

    console.print(f"[green]Daemon started.[/green] Scanning every 6 hours. Daily digest at {digest_time}.")
    console.print("Press Ctrl+C to stop.\n")

    run_search()
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon stopped.[/yellow]")


def _matches_season_filter(title: str, config: dict) -> bool:
    """Return False if the listing title matches any excluded pattern."""
    import re
    title_lower = title.lower()
    for pattern in config.get("search", {}).get("exclude_title_patterns", []):
        if re.search(pattern, title_lower):
            return False
    return True


def _upsert_listings(db, listings, config: dict = None) -> int:
    new_count = 0
    for listing in listings:
        if config and not _matches_season_filter(listing.title, config):
            continue
        _, is_new = db.upsert(listing)
        if is_new:
            new_count += 1
    return new_count


def main():
    parser = argparse.ArgumentParser(
        prog="internship-finder",
        description="Austin, TX internship search & application tracker",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Scrape all sources for new listings")
    p_search.set_defaults(func=cmd_search)

    p_list = sub.add_parser("list", help="Show all stored listings")
    p_list.add_argument("--status", help="Filter by status (e.g. new, applied, offer)")
    p_list.set_defaults(func=cmd_list)

    p_stats = sub.add_parser("stats", help="Show application pipeline statistics")
    p_stats.set_defaults(func=cmd_stats)

    p_update = sub.add_parser("update", help="Update the status of a listing")
    p_update.add_argument("id", type=int, help="Listing ID")
    p_update.set_defaults(func=cmd_update)

    p_export = sub.add_parser("export", help="Export listings to CSV")
    p_export.set_defaults(func=cmd_export)

    p_apply = sub.add_parser("apply", help="Auto-fill an application form")
    p_apply.add_argument("id", type=int, help="Listing ID")
    p_apply.set_defaults(func=cmd_apply)

    p_batch = sub.add_parser("batch-apply", help="Open listings in Chrome and track applications")
    p_batch.add_argument("ids", type=int, nargs="+", help="Listing IDs to apply to")
    p_batch.set_defaults(func=cmd_batch_apply)

    p_daemon = sub.add_parser("daemon", help="Run as a background scheduler")
    p_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    config = load_config(args.config)
    args.func(args, config)


if __name__ == "__main__":
    main()

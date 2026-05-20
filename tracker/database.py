import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from scrapers.base import Listing

DB_PATH = Path(__file__).parent.parent / "data" / "internships.db"

STATUSES = [
    "new", "reviewed", "applied", "interview_scheduled",
    "interviewed", "offer", "rejected", "withdrawn",
]


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS listings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT,
                title       TEXT NOT NULL,
                company     TEXT NOT NULL,
                location    TEXT,
                url         TEXT UNIQUE NOT NULL,
                source      TEXT,
                description TEXT,
                salary      TEXT,
                remote      INTEGER DEFAULT 0,
                tags        TEXT,
                date_posted TEXT,
                date_found  TEXT NOT NULL,
                status      TEXT DEFAULT 'new',
                notes       TEXT DEFAULT '',
                applied_at  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_status  ON listings(status);
            CREATE INDEX IF NOT EXISTS idx_company ON listings(company);
            CREATE INDEX IF NOT EXISTS idx_source  ON listings(source);
        """)
        self._conn.commit()

    def upsert(self, listing: Listing) -> tuple:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d = listing.to_dict()
        row = self._conn.execute(
            "SELECT id, status FROM listings WHERE url = ?", (listing.url,)
        ).fetchone()
        if row:
            self._conn.execute(
                """UPDATE listings SET title=?, company=?, location=?, source=?,
                   description=?, salary=?, remote=?, tags=?, date_posted=? WHERE url=?""",
                (d["title"], d["company"], d["location"], d["source"],
                 d["description"], d["salary"], int(listing.remote),
                 d["tags"], d["date_posted"], listing.url),
            )
            self._conn.commit()
            return row["id"], False
        cur = self._conn.execute(
            """INSERT INTO listings
               (job_id, title, company, location, url, source, description,
                salary, remote, tags, date_posted, date_found, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["job_id"], d["title"], d["company"], d["location"], listing.url,
             d["source"], d["description"], d["salary"], int(listing.remote),
             d["tags"], d["date_posted"], now, "new"),
        )
        self._conn.commit()
        return cur.lastrowid, True

    def get_all(self, status: Optional[str] = None) -> list:
        if status:
            return self._conn.execute(
                "SELECT * FROM listings WHERE status=? ORDER BY date_found DESC", (status,)
            ).fetchall()
        return self._conn.execute(
            "SELECT * FROM listings ORDER BY date_found DESC"
        ).fetchall()

    def update_status(self, listing_id: int, status: str, notes: str = "") -> bool:
        if status not in STATUSES:
            return False
        applied_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "applied" else None
        self._conn.execute(
            "UPDATE listings SET status=?, notes=?, applied_at=COALESCE(?,applied_at) WHERE id=?",
            (status, notes, applied_at, listing_id),
        )
        self._conn.commit()
        return True

    def stats(self) -> dict:
        return {
            r["status"]: r["cnt"]
            for r in self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM listings GROUP BY status"
            ).fetchall()
        }

    def get_new_since(self, since: datetime) -> list:
        return self._conn.execute(
            "SELECT * FROM listings WHERE date_found >= ? ORDER BY date_found DESC",
            (since.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()

    def close(self):
        self._conn.close()

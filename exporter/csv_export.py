import csv
from datetime import datetime
from pathlib import Path


def export_to_csv(rows, output_path=None) -> Path:
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(__file__).parent.parent / "data" / f"internships_{ts}.csv"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id", "title", "company", "location", "url", "source",
        "salary", "remote", "tags", "date_posted", "date_found",
        "status", "notes", "applied_at",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))

    return output_path

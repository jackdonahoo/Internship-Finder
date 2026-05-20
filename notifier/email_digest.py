import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_digest(config: dict, new_listings: list) -> bool:
    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled"):
        return False

    sender = email_cfg["sender_email"]
    password = email_cfg["sender_app_password"]
    recipient = email_cfg["recipient_email"]

    subject = (
        f"[Internship Finder] {len(new_listings)} new listing(s) -- {datetime.now().strftime('%b %d, %Y')}"
        if new_listings
        else f"[Internship Finder] No new listings -- {datetime.now().strftime('%b %d, %Y')}"
    )
    body_html = _build_html(new_listings) if new_listings else "<p>No new listings found today.</p>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
        print(f"[Email] Digest sent to {recipient}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send digest: {e}")
        return False


def _build_html(listings) -> str:
    rows = ""
    for i, row in enumerate(listings, 1):
        bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
        rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:8px">{i}</td>'
            f'<td style="padding:8px"><a href="{row["url"]}">{row["title"]}</a></td>'
            f'<td style="padding:8px">{row["company"]}</td>'
            f'<td style="padding:8px">{row["location"]}</td>'
            f'<td style="padding:8px">{row["source"]}</td>'
            f'<td style="padding:8px">{row.get("date_posted", "")}</td>'
            f'</tr>'
        )
    return f"""
    <html><body>
    <h2 style="color:#2d6cdf">New Austin Internship Listings</h2>
    <p>Found <strong>{len(listings)}</strong> new listing(s) since your last scan.</p>
    <table border="0" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px">
        <thead><tr style="background:#2d6cdf;color:#fff">
            <th style="padding:8px">#</th><th style="padding:8px">Title</th>
            <th style="padding:8px">Company</th><th style="padding:8px">Location</th>
            <th style="padding:8px">Source</th><th style="padding:8px">Posted</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <p style="color:#888;font-size:11px;margin-top:24px">Sent by Internship Finder -- Austin, TX</p>
    </body></html>"""

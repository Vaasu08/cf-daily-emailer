"""
app.py
------
The website: lets a user sign up with an email + a chosen Codeforces rating.
Also exposes a /send-daily endpoint that PythonAnywhere's Scheduled Task
will call once a day to actually send the emails.

Basic Flask + SQLite. No frameworks beyond Flask itself.
"""

import json
import os
import random
import smtplib
import sqlite3
from datetime import datetime
from email.mime.text import MIMEText

from dotenv import load_dotenv
from flask import Flask, g, redirect, render_template, request, url_for

load_dotenv()  # loads GMAIL_* from .env in this folder (local setup)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Config -- these come from environment variables you set in PythonAnywhere's
# "Web" tab (or a .env file locally). NEVER hardcode real values here.
# ---------------------------------------------------------------------------
DATABASE_PATH = os.environ.get("DATABASE_PATH", "users.db")
PROBLEMS_FILE = os.environ.get("PROBLEMS_FILE", "problems.json")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")        # your Gmail address
# Google shows app passwords in 4 groups; spaces are ignored
_raw_app_pw = os.environ.get("GMAIL_APP_PASSWORD") or ""
GMAIL_APP_PASSWORD = _raw_app_pw.replace(" ", "") or None
# A shared secret so random people on the internet can't trigger your emails
# by guessing the /send-daily URL. Set this to any random string yourself.
SEND_DAILY_SECRET = os.environ.get("SEND_DAILY_SECRET", "change-me")

VALID_RATINGS = [800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the users table if it doesn't exist yet. Safe to call every startup."""
    db = sqlite3.connect(DATABASE_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            rating INTEGER NOT NULL,
            -- comma-separated list of problem URLs already sent, for cycling
            sent_urls TEXT NOT NULL DEFAULT ''
        )
        """
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Problem selection logic: cycle through all problems at a rating before
# repeating any (as decided).
# ---------------------------------------------------------------------------
def load_problems():
    with open(PROBLEMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_next_problem(user_row, all_problems):
    """
    Given a user's row (with their rating + already-sent urls) and the full
    problem list, return the next problem dict to send them.
    Cycles: once every problem at that rating has been sent, the sent-list
    resets and cycling starts over.
    """
    candidates = [p for p in all_problems if p["rating"] == user_row["rating"]]
    if not candidates:
        return None  # no problems seeded at this rating

    already_sent = set(user_row["sent_urls"].split(",")) if user_row["sent_urls"] else set()
    remaining = [p for p in candidates if p["url"] not in already_sent]

    if not remaining:
        # Full cycle completed -- start over
        remaining = candidates
        already_sent = set()

    chosen = random.choice(remaining)
    already_sent.add(chosen["url"])

    return chosen, already_sent


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------
def send_email(to_address, subject, body):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set in environment variables."
        )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [to_address], msg.as_string())


def build_email_body(problem):
    return (
        f"Today's Codeforces problem for you:\n\n"
        f"{problem['name']} (Rating: {problem['rating']})\n"
        f"{problem['url']}\n\n"
        f"Good luck! -- Your Daily CF Problem Bot"
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", ratings=VALID_RATINGS, year=datetime.now().year)


@app.route("/signup", methods=["POST"])
def signup():
    email = request.form.get("email", "").strip().lower()
    rating = request.form.get("rating", "")

    try:
        rating = int(rating)
    except ValueError:
        return render_template(
            "index.html",
            ratings=VALID_RATINGS,
            error="Please choose a valid rating.",
            year=datetime.now().year,
        )

    if not email or "@" not in email:
        return render_template(
            "index.html",
            ratings=VALID_RATINGS,
            error="Please enter a valid email.",
            year=datetime.now().year,
        )

    if rating not in VALID_RATINGS:
        return render_template(
            "index.html",
            ratings=VALID_RATINGS,
            error="Please choose a valid rating.",
            year=datetime.now().year,
        )

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (email, rating, sent_urls) VALUES (?, ?, '')",
            (email, rating),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # Email already signed up -- update their rating instead of erroring out
        db.execute(
            "UPDATE users SET rating = ?, sent_urls = '' WHERE email = ?",
            (rating, email),
        )
        db.commit()

    return render_template("success.html", email=email, rating=rating, year=datetime.now().year)


@app.route("/send-daily", methods=["POST", "GET"])
def send_daily():
    """
    Called once a day by a PythonAnywhere Scheduled Task (see README).
    Protected by a shared secret passed as ?secret=... so randoms can't
    trigger it by hitting the URL.
    """
    secret = request.args.get("secret", "")
    if secret != SEND_DAILY_SECRET:
        return "Forbidden", 403

    all_problems = load_problems()
    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()

    sent_count = 0
    errors = []

    for user in users:
        result = pick_next_problem(user, all_problems)
        if result is None:
            errors.append(f"{user['email']}: no problems seeded at rating {user['rating']}")
            continue

        problem, updated_sent_set = result
        body = build_email_body(problem)

        try:
            send_email(user["email"], f"Today's CF Problem: {problem['name']}", body)
            db.execute(
                "UPDATE users SET sent_urls = ? WHERE id = ?",
                (",".join(updated_sent_set), user["id"]),
            )
            db.commit()
            sent_count += 1
        except Exception as e:  # noqa: BLE001 -- we want to log & continue, not crash the batch
            errors.append(f"{user['email']}: {e}")

    return {
        "sent": sent_count,
        "total_users": len(users),
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
init_db()

if __name__ == "__main__":
    app.run(debug=True)

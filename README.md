# Daily Codeforces Problem Emailer

A small website where anyone can sign up with their email + a chosen
Codeforces rating (800–1900), and get one random problem from that rating
emailed to them every day. Cycles through every problem at that rating
before repeating any.

**Design note:** the UI uses a dark, terminal-inspired look with a
color-coded rating ladder (echoing Codeforces' own rating-tier colors).
I could not take an actual screenshot of it in this environment (no
browser access here), so give the homepage a look yourself after step 3
below and tell me if anything needs adjusting — spacing, colors, copy,
whatever.

## Files
- `app.py` — the Flask website + the `/send-daily` endpoint that actually sends emails
- `problems.json` — the problem database (120 problems, 10 per rating from 800–1900)
- `verify_problems.py` — run this once to double-check every problem's rating against the live Codeforces API
- `templates/index.html` — signup page (rating ladder + email field)
- `templates/success.html` — confirmation page
- `static/style.css` — all styling, one file, no build step needed
- `requirements.txt` — just Flask

## Step 0 — Run it locally first (recommended before touching PythonAnywhere)

```bash
cd cf-daily-emailer
pip install -r requirements.txt
python3 app.py
```

Open http://127.0.0.1:5000 in your browser — you'll see the live signup
page. Try signing up, check the confirmation page, tweak `static/style.css`
or the templates and refresh to see changes instantly (Flask's dev server
reloads on save when run this way).

A `users.db` SQLite file will appear in the folder the first time you run
it — that's your local database, safe to delete anytime to start fresh
(`rm users.db`).

Email sending won't work locally until you complete Step 2 and fill in
the `.env` file in this folder (copy from `.env.example` if needed):

```
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=your16charapppassword
SEND_DAILY_SECRET=pick-any-random-string
```

Spaces in the Google app password are optional — paste it as shown or
as 16 characters with no spaces. Then run `python app.py` and visit
`http://127.0.0.1:5000/send-daily?secret=pick-any-random-string`
to send real emails to whoever's signed up locally.

## Step 1 — Verify the problem database

```bash
pip install -r requirements.txt
python3 verify_problems.py
```

This hits the real Codeforces API and tells you if any problem's rating
label is wrong, or any URL is broken. I seeded `problems.json` from memory
and a couple of searches, so treat this as a required check, not optional
— fix or delete any flagged entries in `problems.json` before going live.

## Step 2 — Get a Gmail App Password

1. Go to https://myaccount.google.com/apppasswords (your Gmail needs
   2-Step Verification turned on first — https://myaccount.google.com/signinoptions/two-step-verification)
2. Create an app password for "Mail"
3. Copy the 16-character code somewhere safe. You'll paste it into
   PythonAnywhere's environment variables in Step 4 — never into the code
   itself, and never share it in chat with anyone (including me).

## Step 3 — Upload to PythonAnywhere

1. Sign up free at https://www.pythonanywhere.com
2. Open a **Bash console** from your dashboard
3. Upload this whole folder — easiest way: create a GitHub repo with these
   files and run `git clone <your-repo-url>` inside the Bash console. (Or
   use the Files tab to upload each file manually.)
4. In the Bash console, inside the project folder:
   ```bash
   pip install --user -r requirements.txt
   ```

## Step 4 — Set up the Web App

1. Go to the **Web** tab → **Add a new web app** → choose **Flask** → Python 3.10+
2. Set the source code path to your uploaded folder
3. In the **WSGI configuration file** it gives you, make sure it points to
   your `app.py`'s `app` object (PythonAnywhere's template shows you the
   exact line to edit — it's usually `from app import app as application`)
4. Scroll to **Environment variables** on the Web tab and add:
   - `GMAIL_ADDRESS` = your Gmail address
   - `GMAIL_APP_PASSWORD` = the 16-character app password from Step 2
   - `SEND_DAILY_SECRET` = make up any random string (e.g. a long password) — this protects your `/send-daily` endpoint from strangers
5. Click **Reload** on the Web tab. Visit your `<yourusername>.pythonanywhere.com` URL — you should see the signup form.

## Step 5 — Set up the daily Scheduled Task

1. Go to the **Tasks** tab on PythonAnywhere (free accounts get 1 daily scheduled task)
2. Set the time you want the email to go out daily (in UTC — convert from your timezone)
3. Command to run:
   ```bash
   curl "https://<yourusername>.pythonanywhere.com/send-daily?secret=<YOUR_SEND_DAILY_SECRET>"
   ```
   (replace both placeholders with your actual subdomain and secret)
4. Save. That's it — PythonAnywhere will hit that URL every day, which
   triggers the email-sending logic in `app.py`.

## Testing it manually before relying on the schedule

Visit this URL yourself in a browser (or `curl` it) any time to trigger an
immediate send to all signed-up users, to confirm it works:
```
https://<yourusername>.pythonanywhere.com/send-daily?secret=<YOUR_SECRET>
```
It returns a small JSON report: how many emails sent, how many users total,
and any errors (e.g. wrong Gmail password shows up here immediately).

## Notes / limitations (kept intentionally basic)
- No unsubscribe link yet — you said keep it minimal. Add one later if needed.
- No admin panel — to see signed-up users, use a PythonAnywhere Bash console:
  `sqlite3 users.db "SELECT * FROM users;"`
- Confirmed with PythonAnywhere's own support forum: free accounts block
  most outbound SMTP, but they specifically allowlist Gmail's servers as
  an exception. So `smtp.gmail.com:465` should work on the free tier.
  One known quirk (also from their staff): Gmail's IP addresses change
  periodically, and PythonAnywhere's firewall allowlist can lag behind
  by a bit, which occasionally causes a "Network is unreachable" error
  for a short window. If a day's email fails, check the `/send-daily`
  JSON response for the exact error — if it says "Network is unreachable,"
  it's almost certainly this, and it typically self-resolves within a day.
- 120 problems total, 10 per rating. Add more anytime by editing `problems.json` (same `{"rating": ..., "name": ..., "url": ...}` shape) — no code changes needed.

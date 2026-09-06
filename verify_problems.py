"""
verify_problems.py
-------------------
Run this ONCE before going live (and any time you edit problems.json).

It checks every problem in problems.json against the real, live Codeforces
API (https://codeforces.com/api/problemset.problems) and reports:
  - problems whose URL doesn't match a real Codeforces problem
  - problems whose actual CF rating differs from what we've labeled them

This does NOT modify problems.json automatically -- it just prints a report
so you can manually fix any mismatches. That's intentional: silently
"correcting" data is riskier than showing you exactly what's wrong.

Usage:
    python3 verify_problems.py
"""

import json
import re
import urllib.request

CF_API_URL = "https://codeforces.com/api/problemset.problems"
PROBLEMS_FILE = "problems.json"


def fetch_real_cf_ratings():
    """Fetch the full CF problemset and return {(contest_id, index): rating}."""
    with urllib.request.urlopen(CF_API_URL, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if data.get("status") != "OK":
        raise RuntimeError("Codeforces API did not return OK status")

    lookup = {}
    for p in data["result"]["problems"]:
        key = (p["contestId"], p["index"])
        lookup[key] = p.get("rating")  # rating may be missing for some problems
    return lookup


def parse_contest_and_index(url):
    """Extract (contest_id, index) from a codeforces.com/problemset/problem/X/Y URL."""
    m = re.search(r"/problem/(\d+)/([A-Za-z0-9]+)", url)
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def main():
    with open(PROBLEMS_FILE, "r", encoding="utf-8") as f:
        problems = json.load(f)

    print(f"Loaded {len(problems)} problems from {PROBLEMS_FILE}")
    print("Fetching live Codeforces problem ratings (this can take a few seconds)...")
    real_ratings = fetch_real_cf_ratings()
    print(f"Fetched {len(real_ratings)} problems from the live Codeforces API.\n")

    not_found = []
    mismatched = []
    ok_count = 0

    for p in problems:
        parsed = parse_contest_and_index(p["url"])
        if not parsed:
            not_found.append((p, "Could not parse contest/index from URL"))
            continue

        key = parsed
        if key not in real_ratings:
            not_found.append((p, f"No problem {key[0]}{key[1]} found on Codeforces"))
            continue

        real_rating = real_ratings[key]
        if real_rating is None:
            mismatched.append((p, "Problem exists but has no official rating on CF"))
        elif real_rating != p["rating"]:
            mismatched.append((p, f"Labeled {p['rating']}, but CF says {real_rating}"))
        else:
            ok_count += 1

    print(f"✅ {ok_count} problems confirmed correct\n")

    if not_found:
        print(f"❌ {len(not_found)} problems NOT FOUND on Codeforces (broken URL/ID):")
        for p, reason in not_found:
            print(f"   - [{p['rating']}] {p['name']} ({p['url']}) -> {reason}")
        print()

    if mismatched:
        print(f"⚠️  {len(mismatched)} problems with a RATING MISMATCH:")
        for p, reason in mismatched:
            print(f"   - [{p['rating']}] {p['name']} ({p['url']}) -> {reason}")
        print()

    if not not_found and not mismatched:
        print("Everything checks out. problems.json is safe to use as-is.")
    else:
        print("Fix the above manually in problems.json before deploying,")
        print("or just delete flagged entries -- 120 problems is more than enough")
        print("even if you drop a handful.")


if __name__ == "__main__":
    main()

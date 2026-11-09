#!/usr/bin/env python3
"""
Score scraped Instagram posts using the Anthropic API.
Scores each post on the 5-question content rubric and checks against 7 Celebration values.

Reads:  data/posts_YYYY-MM-DD.json
Writes: data/scores_YYYY-MM-DD.json

Usage:
  ANTHROPIC_API_KEY=sk-ant-... python scripts/score_posts.py
  python scripts/score_posts.py --date 2026-11-02   # specific week
"""

import anthropic, json, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_DIR = Path(__file__).parent.parent
DATA_DIR = REPO_DIR / "data"

# ── Scoring rubric ────────────────────────────────────────────────────────────
RUBRIC = """
You score Instagram posts for Celebration Church (Austin, Texas) — a multi-campus church.
Score the caption on exactly 5 criteria. Each is 0, 1, or 2 points.

CRITERIA (read them carefully — the differences matter):

1. SCROLL-STOPPER (0–2)
   2 = Caption implies a compelling real moment: real people, raw emotion, something happening
   1 = Some visual potential but generic or staged-feeling
   0 = Pure text graphic, placeholder image, or no visual cue at all

2. ONE CLEAR MESSAGE (0–2)
   2 = A stranger reads it in 3 seconds and knows exactly what it's about
   1 = The idea is there but buried in multiple things
   0 = Unclear, contradictory, or no message at all

3. POINTS TO CHRIST, CHURCH, OR CALLING (0–2)
   2 = Explicitly says WHY it matters — connects to faith, purpose, or life transformation
   1 = Implies it weakly, or mentions Christ/church as a backdrop without saying why
   0 = Pure logistics or self-congratulation with no faith connection

4. DOOR OPEN TO SOMEONE NEW (0–2)
   2 = No insider language; a person who has never attended would feel personally invited
   1 = Mostly accessible but uses one insider term ("Celebration Family", program name) or assumes attendance
   0 = Written only for current members; a newcomer wouldn't know what to do with it

5. CLEAR NEXT STEP (0–2)
   2 = Specific action with at least two of: time, place, link, or what to bring
   1 = Vague next step ("come join us") or only one of time/place/link
   0 = No next step at all

CELEBRATION'S 7 VALUES (list only those clearly present in this post — absent means absent):
- Jesus is our Pursuit
- Scripture is our Authority
- The Holy Spirit is our Power
- People are our Heart
- Service is our Privilege
- Generosity is our Lifestyle
- Flourishing is our Goal

CAPTION TO SCORE:
{caption}

Return ONLY valid JSON, no explanation, no markdown:
{{
  "scores": [s1, s2, s3, s4, s5],
  "total": <sum 0–10>,
  "values_present": ["value name", ...],
  "one_line": "<10–15 word honest read of this post>",
  "reasoning": "<2–3 sentences explaining the score>"
}}
"""

CATEGORIES = {(8,10): "Motivating", (5,7): "Informing", (0,4): "Noise"}

def categorize(total):
    for (lo, hi), label in CATEGORIES.items():
        if lo <= total <= hi:
            return label
    return "Noise"

def get_week_start(date_arg=None):
    if date_arg:
        return datetime.strptime(date_arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    today = datetime.now(timezone.utc)
    return (today - timedelta(days=today.weekday() + 7)).replace(hour=0, minute=0, second=0)

def score_post(client, post):
    """Call Claude to score one post. Returns dict with scores + analysis."""
    caption = post.get("caption", "").strip()
    if not caption:
        return {"scores": [0,0,0,0,0], "total": 0, "values_present": [],
                "one_line": "No caption", "reasoning": "Empty caption.", "category": "Noise"}

    prompt = RUBRIC.format(caption=caption[:1500])  # cap at 1500 chars

    for attempt in range(3):
        try:
            resp = client.messages.create(
                model="claude-haiku-20240307",  # fast + cheap for scoring
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp.content[0].text.strip()
            # Strip markdown fences if present
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            result["total"] = sum(result.get("scores", [0]*5))
            result["category"] = categorize(result["total"])
            return result
        except (json.JSONDecodeError, KeyError, Exception) as e:
            if attempt == 2:
                return {"scores": [0,0,0,0,0], "total": 0, "values_present": [],
                        "one_line": "Score error", "reasoning": str(e), "category": "Error"}
            time.sleep(1)

def build_account_summary(handle, posts_with_scores):
    """Aggregate per-post scores into an account-level summary."""
    scored = [p for p in posts_with_scores if p.get("total", 0) > 0 or p.get("category") == "Noise"]
    if not scored:
        return {"handle": handle, "post_count": 0, "avg_score": None,
                "category": "—", "values_seen": [], "top_post": None, "weak_post": None}

    totals = [p["total"] for p in scored]
    avg = round(sum(totals) / len(totals), 1)

    # Aggregate values across all posts
    values_seen = list(set(v for p in scored for v in p.get("values_present", [])))

    # Best and worst posts
    top  = max(scored, key=lambda p: p["total"])
    weak = min(scored, key=lambda p: p["total"])

    return {
        "handle":      handle,
        "post_count":  len(scored),
        "avg_score":   avg,
        "category":    categorize(round(avg)),
        "values_seen": values_seen,
        "top_post":    {"url": top.get("url"), "caption": top.get("caption","")[:200],
                        "total": top["total"], "one_line": top.get("one_line",""),
                        "likes": top.get("likes", 0), "comments": top.get("comments", 0)},
        "weak_post":   {"url": weak.get("url"), "caption": weak.get("caption","")[:200],
                        "total": weak["total"], "one_line": weak.get("one_line","")},
    }

def build_network_summary(account_summaries, all_posts_scored):
    """Network-level roll-up."""
    scored_accts = [a for a in account_summaries if a["avg_score"] is not None]

    all_scores   = [p["total"] for p in all_posts_scored if "total" in p]
    total_posts  = len(all_posts_scored)
    network_avg  = round(sum(all_scores) / len(all_scores), 1) if all_scores else None

    # Category breakdown
    cats = {"Motivating": 0, "Informing": 0, "Noise": 0}
    for p in all_posts_scored:
        c = p.get("category", "Noise")
        if c in cats: cats[c] += 1

    # Values across network
    all_values = {}
    for p in all_posts_scored:
        for v in p.get("values_present", []):
            all_values[v] = all_values.get(v, 0) + 1

    all_seven = [
        "Jesus is our Pursuit", "Scripture is our Authority", "The Holy Spirit is our Power",
        "People are our Heart", "Service is our Privilege", "Generosity is our Lifestyle",
        "Flourishing is our Goal"
    ]
    values_check = {v: all_values.get(v, 0) for v in all_seven}

    return {
        "network_avg":    network_avg,
        "total_posts":    total_posts,
        "category_breakdown": cats,
        "values_check":   values_check,
        "accounts":       account_summaries,
    }

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Find posts file
    date_arg = None
    for arg in sys.argv[1:]:
        if re.match(r"\d{4}-\d{2}-\d{2}", arg):
            date_arg = arg

    week_start = get_week_start(date_arg)
    posts_file = DATA_DIR / f"posts_{week_start.strftime('%Y-%m-%d')}.json"

    if not posts_file.exists():
        print(f"ERROR: No posts file found at {posts_file}")
        print("Run scrape_ig_posts.py first.")
        sys.exit(1)

    posts = json.loads(posts_file.read_text())
    print(f"Scoring {len(posts)} posts from {posts_file.name}")

    # Group by account
    by_account = {}
    for p in posts:
        h = p["handle"]
        by_account.setdefault(h, []).append(p)

    all_scored = []
    account_summaries = []

    for acct in [a["handle"] for a in [
        {"handle": "@txcelebration"}, {"handle": "@wave.students"},
        {"handle": "@celebration.georgetown"}, {"handle": "@celebration.leander"},
        {"handle": "@celebration.centralaustin"}, {"handle": "@celebration.laketravis"},
    ]]:
        acct_posts = by_account.get(acct, [])
        scored = []

        if not acct_posts:
            print(f"\n{acct}: no posts this week")
            account_summaries.append({
                "handle": acct, "post_count": 0, "avg_score": None,
                "category": "—", "values_seen": [], "top_post": None, "weak_post": None
            })
            continue

        print(f"\n{acct}: scoring {len(acct_posts)} posts")
        for p in acct_posts:
            result = score_post(client, p)
            merged = {**p, **result}
            scored.append(merged)
            all_scored.append(merged)
            print(f"  {result['total']}/10 [{result['category']}] — {result.get('one_line','')}")
            time.sleep(0.3)  # rate limit courtesy

        summary = build_account_summary(acct, scored)
        account_summaries.append(summary)
        print(f"  → avg {summary['avg_score']}/10 ({summary['category']})")

    network = build_network_summary(account_summaries, all_scored)

    # Save
    out = {
        "week_start": week_start.strftime("%Y-%m-%d"),
        "generated":  datetime.now().isoformat(),
        "network":    network,
        "posts":      all_scored,
    }
    out_file = DATA_DIR / f"scores_{week_start.strftime('%Y-%m-%d')}.json"
    out_file.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\n✓ Saved → {out_file}")
    print(f"  Network avg: {network['network_avg']}/10 ({network['total_posts']} posts)")
    print(f"  Breakdown: {network['category_breakdown']}")

import re
if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Celebration Church — Weekly Social Media Report Generator
Scrapes Meta Business Suite via Playwright (text extraction approach).
Commits the report to GitHub and updates the index.

Usage: python scrape_and_report.py
       GITHUB_TOKEN=xxx python scrape_and_report.py

Setup:
  pip install playwright
  playwright install chromium
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
REPO_DIR    = Path(__file__).parent.parent
REPORTS_DIR = REPO_DIR / "reports"
TEMPLATE    = REPORTS_DIR / "template.html"
INDEX_PATH  = REPO_DIR / "index.html"
INDEX_JSON  = REPORTS_DIR / "index.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = "anzalonemedia/celebration-social-reports"

# Meta Business Suite base URL (use "last_week" timeframe)
BIZ_SUITE_URL = "https://business.facebook.com/latest/insights/overview/?timeframe=last_week"

# Instagram accounts to track
# asset_id is the numeric Facebook Page/IG asset ID — we pull it from the URL
# when switching accounts in Business Suite. Leave blank and the script will
# use the account switcher flow instead.
ACCOUNTS = [
    {"name": "Celebration Church (TX)",   "platform": "ig", "handle": "@txcelebration",           "ig_username": "txcelebration"},
    {"name": "Celebration Georgetown",     "platform": "ig", "handle": "@celebration.georgetown",  "ig_username": "celebration.georgetown"},
    {"name": "Celebration Leander",        "platform": "ig", "handle": "@celebration.leander",    "ig_username": "celebration.leander"},
    {"name": "Celebration Lake Travis",    "platform": "ig", "handle": "@celebration.laketravis", "ig_username": "celebration.laketravis"},
    {"name": "Celebration Central Austin", "platform": "ig", "handle": "@celebration.centralaustin","ig_username": "celebration.centralaustin"},
    {"name": "Austin Collective",          "platform": "ig", "handle": "@austincollective.tx",    "ig_username": "austincollective.tx"},
    {"name": "Wave Students",              "platform": "ig", "handle": "@wave.students",          "ig_username": "wave.students"},
]

# ── Week helpers ──────────────────────────────────────────────────────────────
def get_week_range():
    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday

def fmt_date(d):   return d.strftime("%B %-d, %Y")
def fmt_num(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)
def delta_class(v): return "up" if v > 0 else ("down" if v < 0 else "neutral")
def delta_str(v):   return f"+{v:,}" if v > 0 else f"{v:,}"

# ── Text-based metric parser ──────────────────────────────────────────────────
def parse_num(text):
    """Convert '90.4K', '3.5K', '2K', '32,471', '71' → int."""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    m = re.match(r"([\d.]+)([KkMm]?)", text)
    if not m:
        return 0
    val = float(m.group(1))
    suffix = m.group(2).upper()
    if suffix == "K": val *= 1_000
    if suffix == "M": val *= 1_000_000
    return int(val)

def extract_metrics_from_text(page_text):
    """
    Parse visible text from Meta Business Suite insights overview.
    The page renders metrics in a consistent pattern:
      MetricLabel\nValue\nPercentChange%
    We extract each known metric by searching for its label then grabbing
    the next numeric token.
    """
    lines = [l.strip() for l in page_text.splitlines() if l.strip()]

    def find_metric(label_patterns, lines):
        """Find first numeric value after any of the label patterns."""
        for i, line in enumerate(lines):
            for pat in label_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    # Look at next few lines for a number
                    for j in range(i+1, min(i+5, len(lines))):
                        candidate = lines[j]
                        # Match: 90.4K, 3.5K, 2K, 32,471, 71, 0
                        if re.match(r"^[\d,]+\.?\d*[KkMm]?$", candidate):
                            return parse_num(candidate)
            return None

    views        = find_metric([r"^Views$"], lines) or 0
    viewers      = find_metric([r"^Viewers$"], lines) or 0
    follows      = find_metric([r"^Follows$", r"^Net follows$"], lines) or 0
    unfollows    = find_metric([r"^Unfollows$"], lines) or 0
    interactions = find_metric([r"^Content interactions$", r"^Interactions$"], lines) or 0
    reach        = viewers  # Business Suite now shows "Viewers" instead of "Reach"

    # Net followers = follows - unfollows
    net_followers = follows - unfollows

    # Count posts from "Recent content" section
    posts_count = len(re.findall(r"(Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+\w+\s+\d+,\s+\d+:\d+[ap]m", page_text))

    return {
        "reach":        reach,
        "impressions":  views,
        "engagement":   interactions,
        "followers":    0,   # requires separate page load (profile page)
        "new_followers": net_followers,
        "posts_count":  posts_count,
        "top_post":     extract_top_post_from_text(page_text),
    }

def extract_top_post_from_text(page_text):
    """Extract top post caption and stats from the Recent content section."""
    # Find the Recent content section
    m = re.search(r"Recent content\nSee all content\n(.+?)(?:\nRecommendations|\Z)", page_text, re.DOTALL)
    if not m:
        return None
    section = m.group(1)

    # First content item: caption followed by date, then 4 numbers (views, reach, comments, likes)
    lines = [l.strip() for l in section.splitlines() if l.strip()]
    if not lines:
        return None

    caption = lines[0]
    # Find date line
    date_idx = None
    for i, l in enumerate(lines):
        if re.match(r"(Sun|Mon|Tue|Wed|Thu|Fri|Sat)\s+\w+\s+\d+,", l):
            date_idx = i
            break

    nums = []
    if date_idx is not None:
        for l in lines[date_idx+1:date_idx+6]:
            if re.match(r"^[\d,]+\.?\d*[KkMm]?$", l):
                nums.append(parse_num(l))

    return {
        "caption":   caption[:300],
        "reach":     nums[1] if len(nums) > 1 else 0,
        "likes":     nums[3] if len(nums) > 3 else 0,
        "url":       "",
        "thumbnail": "",
    }

# ── Playwright scraper ────────────────────────────────────────────────────────
def scrape_all_accounts():
    """
    Uses Playwright to open Meta Business Suite and scrape each account.
    Connects to existing Chrome session (--remote-debugging-port=9222) if available,
    otherwise launches a new browser and waits for the user to log in.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    results = []

    with sync_playwright() as p:
        # Try to connect to an existing Chrome session first
        browser = None
        context = None
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0] if browser.contexts else None
            print("✓ Connected to existing Chrome session")
        except Exception:
            pass

        if not context:
            print("Launching new browser — log in to Meta Business Suite when prompted")
            browser = p.chromium.launch(headless=False, slow_mo=300)
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

        page = context.new_page()

        # First load — may need login
        print("Loading Meta Business Suite...")
        page.goto(BIZ_SUITE_URL, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_timeout(2000)

        # Check if we need to log in
        if "login" in page.url.lower() or "checkpoint" in page.url.lower():
            print("\n⚠ Not logged in — please log in to Facebook/Meta Business Suite in the browser window")
            print("Waiting up to 60 seconds for login...")
            try:
                page.wait_for_url("**/business.facebook.com/**", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=15000)
            except PWTimeout:
                print("Login timed out. Run again after logging in.")
                sys.exit(1)

        # Switch to Instagram view if needed
        try:
            # Click the platform switcher (shows "Facebook" or "Instagram")
            platform_btn = page.locator("text=Facebook").first
            if platform_btn.is_visible(timeout=3000):
                platform_btn.click()
                page.wait_for_timeout(1000)
                ig_option = page.locator("text=Instagram").first
                if ig_option.is_visible(timeout=3000):
                    ig_option.click()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    page.wait_for_timeout(2000)
                    print("✓ Switched to Instagram view")
        except Exception as e:
            print(f"Note: Could not switch platform selector: {e}")

        # Now scrape each account via the account switcher
        for account in ACCOUNTS:
            print(f"\nScraping {account['name']} ({account['handle']})...")
            try:
                metrics = scrape_one_account(page, account)
                results.append({**account, **metrics})
                print(f"  ✓ Views: {fmt_num(metrics.get('impressions',0))}  "
                      f"Interactions: {fmt_num(metrics.get('engagement',0))}  "
                      f"Net followers: {delta_str(metrics.get('new_followers',0))}")
            except Exception as e:
                print(f"  ⚠ Failed: {e}")
                results.append({**account,
                    "reach": 0, "impressions": 0, "engagement": 0,
                    "followers": 0, "new_followers": 0, "posts_count": 0,
                    "top_post": None, "error": str(e)})

        try:
            page.close()
        except Exception:
            pass

    return results


def scrape_one_account(page, account):
    """Switch to the given account and scrape its insights overview."""
    from playwright.sync_api import TimeoutError as PWTimeout

    # Use the account switcher at the top of Business Suite
    # Click the current account name to open the switcher
    try:
        # The switcher is typically in the left sidebar or top bar
        # Try clicking the account name text
        switcher = page.locator("[role='button']").filter(has_text=re.compile(r"Celebration|Collective|Wave", re.I)).first
        if switcher.is_visible(timeout=2000):
            switcher.click()
            page.wait_for_timeout(1000)

            # Search for or click the account
            search = page.locator("input[placeholder*='Search']").first
            if search.is_visible(timeout=2000):
                search.fill(account["ig_username"].replace(".", " "))
                page.wait_for_timeout(1000)

            # Click the matching account option
            option = page.locator(f"text={account['ig_username']}").first
            if not option.is_visible(timeout=2000):
                option = page.locator(f"text={account['name']}").first
            option.click()
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(2000)
    except Exception:
        # If switcher fails, try navigating with asset_id in URL if we have it
        if account.get("asset_id"):
            page.goto(f"{BIZ_SUITE_URL}&asset_id={account['asset_id']}", timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(2000)
        # Otherwise stay on current account and log the issue
        else:
            pass

    # Extract all visible text and parse metrics
    page_text = page.inner_text("body")
    return extract_metrics_from_text(page_text)

# ── Report builder ────────────────────────────────────────────────────────────
def build_report(account_data):
    week_start, week_end = get_week_range()
    week_label   = f"{fmt_date(week_start)} – {fmt_date(week_end)}"
    generated_at = datetime.now().strftime("%B %-d, %Y at %-I:%M %p")

    total_reach       = sum(a.get("reach", 0) for a in account_data)
    total_impressions = sum(a.get("impressions", 0) for a in account_data)
    total_engagement  = sum(a.get("engagement", 0) for a in account_data)
    total_posts       = sum(a.get("posts_count", 0) for a in account_data)
    total_followers   = sum(a.get("followers", 0) for a in account_data)
    net_followers     = sum(a.get("new_followers", 0) for a in account_data)
    avg_eng_rate      = round((total_engagement / total_impressions * 100) if total_impressions else 0, 2)

    ig_views = sum(a.get("impressions", 0) for a in account_data if a["platform"] == "ig")
    fb_views = sum(a.get("impressions", 0) for a in account_data if a["platform"] == "fb")
    top_platform = "Instagram" if ig_views >= fb_views else "Facebook"

    best_post_reach, best_post_account = 0, ""
    for a in account_data:
        tp = a.get("top_post") or {}
        if tp.get("reach", 0) > best_post_reach:
            best_post_reach   = tp["reach"]
            best_post_account = a["name"]

    # Reach bars
    max_r = max((a.get("impressions", 0) for a in account_data), default=1) or 1
    reach_bars = ""
    for a in sorted(account_data, key=lambda x: x.get("impressions", 0), reverse=True):
        pct   = round(a.get("impressions", 0) / max_r * 100)
        color = "orange" if a["platform"] == "ig" else ""
        reach_bars += f"""
      <div class="bar-row">
        <div class="bar-name" title="{a['name']}">{a['name']}</div>
        <div class="bar-track"><div class="bar-fill {color}" style="width:{pct}%"></div></div>
        <div class="bar-value">{fmt_num(a.get('impressions', 0))}</div>
      </div>"""

    # Account cards
    account_cards = ""
    for a in account_data:
        badge    = "IG" if a["platform"] == "ig" else "FB"
        cls      = a["platform"]
        eng_rate = round((a.get("engagement",0) / a.get("impressions",0) * 100)
                         if a.get("impressions",0) else 0, 2)
        nf       = a.get("new_followers", 0)

        tp   = a.get("top_post") or {}
        top_html = ""
        if tp and tp.get("caption"):
            post_link = f'<a class="top-post-link" href="{tp["url"]}" target="_blank">View post →</a>' if tp.get("url") else ""
            top_html = f"""
        <div class="top-post-section">
          <div class="top-post-label">Top Post This Week</div>
          <div class="top-post">
            <div class="top-post-img">IMG</div>
            <div class="top-post-content">
              <div class="top-post-caption">{tp['caption'][:200]}</div>
              <div class="top-post-stats">
                <span><strong>{fmt_num(tp.get('reach',0))}</strong> reach</span>
                <span><strong>{fmt_num(tp.get('likes',0))}</strong> likes</span>
              </div>
              {post_link}
            </div>
          </div>
        </div>"""

        err_banner = ""
        if a.get("error"):
            err_banner = f'<div style="padding:0.75rem 1.5rem;background:#fff3cd;color:#856404;font-size:0.8rem">⚠ Scrape error: {a["error"]}</div>'

        account_cards += f"""
      <div class="account-card">
        <div class="account-header">
          <div class="platform-badge {cls}">{badge}</div>
          <div>
            <div class="account-name">{a['name']}</div>
            <div class="account-handle">{a.get('handle','')}</div>
          </div>
        </div>
        {err_banner}
        <div class="account-metrics">
          <div class="metric">
            <div class="m-label">Views</div>
            <div class="m-value">{fmt_num(a.get('impressions',0))}</div>
          </div>
          <div class="metric">
            <div class="m-label">Unique Viewers</div>
            <div class="m-value">{fmt_num(a.get('reach',0))}</div>
          </div>
          <div class="metric">
            <div class="m-label">Interactions</div>
            <div class="m-value">{fmt_num(a.get('engagement',0))}</div>
          </div>
          <div class="metric">
            <div class="m-label">Eng. Rate</div>
            <div class="m-value">{eng_rate}%</div>
          </div>
          <div class="metric">
            <div class="m-label">Net Followers</div>
            <div class="m-value">{delta_str(nf)}</div>
            <div class="m-delta {delta_class(nf)}">this week</div>
          </div>
          <div class="metric">
            <div class="m-label">Posts</div>
            <div class="m-value">{a.get('posts_count',0)}</div>
          </div>
        </div>
        {top_html}
      </div>"""

    # Fill template
    html = TEMPLATE.read_text() \
        .replace("{{WEEK_OF}}",          week_label) \
        .replace("{{GENERATED_DATE}}",   generated_at) \
        .replace("{{ACCOUNT_COUNT}}",    str(len(account_data))) \
        .replace("{{TOTAL_REACH}}",      fmt_num(total_impressions)) \
        .replace("{{TOTAL_IMPRESSIONS}}",fmt_num(total_impressions)) \
        .replace("{{TOTAL_ENGAGEMENT}}", fmt_num(total_engagement)) \
        .replace("{{TOTAL_POSTS}}",      str(total_posts)) \
        .replace("{{NET_FOLLOWERS}}",    delta_str(net_followers)) \
        .replace("{{AVG_ENG_RATE}}",     str(avg_eng_rate)) \
        .replace("{{ENG_DELTA}}",        "+0") \
        .replace("{{ENG_DELTA_CLASS}}",  "neutral") \
        .replace("{{TOP_PLATFORM}}",     top_platform) \
        .replace("{{BEST_POST_REACH}}",  fmt_num(best_post_reach)) \
        .replace("{{BEST_POST_ACCOUNT}}",best_post_account) \
        .replace("{{TOTAL_FOLLOWERS}}",  fmt_num(total_followers)) \
        .replace("{{FOLLOW_DELTA}}",     delta_str(net_followers)) \
        .replace("{{FOLLOW_DELTA_CLASS}}",delta_class(net_followers)) \
        .replace("{{REACH_BARS}}",       reach_bars) \
        .replace("{{ACCOUNT_CARDS}}",    account_cards)

    return html, week_label


def save_report(html, week_label):
    week_start, _ = get_week_range()
    fname = f"week-{week_start.strftime('%Y-%m-%d')}.html"
    (REPORTS_DIR / fname).write_text(html)
    print(f"\n✓ Report saved: reports/{fname}")
    return fname


def update_index(fname, week_label, account_data):
    entries = json.loads(INDEX_JSON.read_text()) if INDEX_JSON.exists() else []
    entries = [{
        "file":        fname,
        "weekOf":      week_label,
        "accounts":    len(account_data),
        "totalPosts":  sum(a.get("posts_count", 0) for a in account_data),
        "totalReach":  sum(a.get("impressions", 0) for a in account_data),
        "generated":   datetime.now().isoformat(),
    }] + [e for e in entries if e["file"] != fname]

    INDEX_JSON.write_text(json.dumps(entries, indent=2))

    # Patch the REPORTS_INDEX placeholder in index.html
    idx = INDEX_PATH.read_text()
    idx = re.sub(r"REPORTS_INDEX", json.dumps(entries), idx)
    INDEX_PATH.write_text(idx)
    print("✓ Index updated")


def git_push(week_label):
    if not GITHUB_TOKEN:
        print("⚠ No GITHUB_TOKEN — skipping push (set env var to enable auto-push)")
        return
    repo_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    cmds = [
        ["git", "-C", str(REPO_DIR), "config", "user.email", "noreply@anthropic.com"],
        ["git", "-C", str(REPO_DIR), "config", "user.name",  "Claude"],
        ["git", "-C", str(REPO_DIR), "add",    "-A"],
        ["git", "-C", str(REPO_DIR), "commit", "-m",
         f"Weekly social report: {week_label}\n\n"
         f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>\n"
         f"Claude-Session: https://claude.ai/code/session_01FREnhoqwbgRoopNEi7GBHY"],
        ["git", "-C", str(REPO_DIR), "push", repo_url, "main"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            print(f"Git error ({' '.join(cmd[3:4])}): {r.stderr.strip()}")
            return
    print("✓ Pushed to GitHub → Cloudflare deploy triggered")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Celebration Church — Weekly Social Report Generator")
    print("=" * 60)
    week_start, week_end = get_week_range()
    print(f"Period: {fmt_date(week_start)} – {fmt_date(week_end)}\n")

    print(f"Scraping {len(ACCOUNTS)} Instagram accounts...")
    account_data = scrape_all_accounts()

    print("\nBuilding report...")
    html, week_label = build_report(account_data)
    fname = save_report(html, week_label)
    update_index(fname, week_label, account_data)

    print("\nPushing to GitHub...")
    git_push(week_label)

    print(f"\n✅ Done — report live at celebration-social-reports.pages.dev")


if __name__ == "__main__":
    main()

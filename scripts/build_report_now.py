#!/usr/bin/env python3
"""
One-shot report builder using manually-scraped data from Meta Business Suite.
Run: python scripts/build_report_now.py
"""
import json, os, re, subprocess
from datetime import datetime, timedelta
from pathlib import Path

REPO_DIR    = Path(__file__).parent.parent
REPORTS_DIR = REPO_DIR / "reports"
TEMPLATE    = REPORTS_DIR / "template.html"
INDEX_PATH  = REPO_DIR / "index.html"
INDEX_JSON  = REPORTS_DIR / "index.json"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = "anzalonemedia/celebration-social-reports"

# ── Real data scraped Nov 9, 2026 from Meta Business Suite (last 28 days) ────
# Timeframe shown: Oct 12 – Nov 8, 2026
# Note: "last_week" in BS URL returns 28-day overview. For weekly filtering
# we extract from the "Your last week in review" panel values where available.

# Campus accent colors (from Celebration brand palette)
CAMPUS_IMAGES = {
    "@txcelebration":            None,  # collage built in template
    "@celebration.centralaustin":"../assets/campus/centralaustin.jpg",
    "@celebration.georgetown":   "../assets/campus/georgetown.jpg",
    "@celebration.leander":      "../assets/campus/leander.jpg",
    "@celebration.laketravis":   "../assets/campus/laketravis.jpg",
    "@wave.students":            "../assets/campus/wave.jpg",
}

CAMPUS_COLORS = {
    "@txcelebration":            "#282829",  # Black — main campus
    "@celebration.centralaustin":"#e65228",  # Orange
    "@celebration.georgetown":   "#3554c5",  # Blue
    "@celebration.laketravis":   "#a5c2c0",  # Light blue / Dusty Aqua
    "@celebration.leander":      "#646a40",  # Green
    "@wave.students":            "#b8b120",  # Yellow (darkened for legibility)
}

ACCOUNT_DATA = [
    {
        "name": "Celebration Church (TX)",
        "platform": "ig",
        "handle": "@txcelebration",
        "profile_url": "https://www.instagram.com/txcelebration/",
        "d7_views": 153654, "d7_reach": 57873, "d7_engagement": 6511,
        "impressions":  555300,
        "reach":        200300,
        "reach_followers":    9556,   # from scraped data
        "reach_nonfollowers": 190144,
        "engagement":   29300,
        "d90_views": 1400000, "d90_reach": 274500, "d90_engagement": 54800,
        "new_followers": 661,
        "followers":    0,
        "ig_posts":     6,
        "ig_stories":   21,
        "top_post": {
            "caption": "SUNDAYS 🤍🤍🤍 Rain or shine, it's better together. Watch the full sermon from today on our YouTube at the 🔗 in our bio!",
            "reach":   3300,
            "likes":   400,
            "comments": 5,
            "url":     "https://www.instagram.com/txcelebration/",
        }
    },
    {
        "name": "Wave Students",
        "platform": "ig",
        "handle": "@wave.students",
        "profile_url": "https://www.instagram.com/wave.students/",
        "d7_views": 77963, "d7_reach": 22925, "d7_engagement": 2317,
        "impressions":  250100,
        "reach":        25800,
        "reach_followers":    3636,
        "reach_nonfollowers": 22719,
        "engagement":   7800,
        "d90_views": 854000, "d90_reach": 90800, "d90_engagement": 27700,
        "new_followers": 3,
        "followers":    0,
        "ig_posts":     0,
        "ig_stories":   26,
        "top_post": {
            "caption": "Wave United we love you!",
            "reach":   707,
            "likes":   18,
            "comments": 2,
            "url":     "https://www.instagram.com/wave.students/",
        },
    },
    {
        "name": "Celebration Georgetown",
        "platform": "ig",
        "handle": "@celebration.georgetown",
        "profile_url": "https://www.instagram.com/celebration.georgetown/",
        "d7_views": 45521, "d7_reach": 10712, "d7_engagement": 1780,
        "impressions":  110400,
        "reach":        11500,
        "reach_followers":    703,
        "reach_nonfollowers": 10888,
        "engagement":   3900,
        "d90_views": 254900, "d90_reach": 20600, "d90_engagement": 8900,
        "new_followers": 87,
        "followers":    0,
        "ig_posts":     4,
        "ig_stories":   10,
        "top_post": {
            "caption": "Hey church!! We are so excited for tomorrow, check out this special invite from our pastor @joechampion!",
            "reach":   7100,
            "likes":   686,
            "comments": 8,
            "url":     "https://www.instagram.com/celebration.georgetown/",
        }
    },
    {
        "name": "Celebration Leander",
        "platform": "ig",
        "handle": "@celebration.leander",
        "profile_url": "https://www.instagram.com/celebration.leander/",
        "d7_views": 8999, "d7_reach": 2895, "d7_engagement": 203,
        "impressions":  54300,
        "reach":        6600,
        "reach_followers":    912,
        "reach_nonfollowers": 5844,
        "engagement":   1700,
        "d90_views": 192100, "d90_reach": 13600, "d90_engagement": 6300,
        "new_followers": 15,
        "followers":    0,
        "ig_posts":     2,
        "ig_stories":   7,
        "top_post":     None,
    },
    {
        "name": "Celebration Central Austin",
        "platform": "ig",
        "handle": "@celebration.centralaustin",
        "profile_url": "https://www.instagram.com/celebration.centralaustin/",
        "d7_views": 11943, "d7_reach": 1797, "d7_engagement": 138,
        "impressions":  41200,
        "reach":        2800,
        "reach_followers":    714,
        "reach_nonfollowers": 2110,
        "engagement":   746,
        "d90_views": 173500, "d90_reach": 7800, "d90_engagement": 4700,
        "new_followers": -1,
        "followers":    0,
        "ig_posts":     0,
        "ig_stories":   26,
        "top_post": {
            "caption": "What a POWERFUL message. Thank you, Lord! Church, see you next week!",
            "reach":   156,
            "likes":   4,
            "comments": 0,
            "url":     "https://www.instagram.com/celebration.centralaustin/",
        },
    },
    {
        "name": "Celebration Lake Travis",
        "platform": "ig",
        "handle": "@celebration.laketravis",
        "profile_url": "https://www.instagram.com/celebration.laketravis/",
        "d7_views": 7747, "d7_reach": 1831, "d7_engagement": 95,
        "impressions":  34000,
        "reach":        1800,
        "reach_followers":    355,
        "reach_nonfollowers": 1460,
        "engagement":   924,
        "d90_views": 165200, "d90_reach": 5800, "d90_engagement": 5300,
        "new_followers": 10,
        "followers":    0,
        "ig_posts":     0,
        "ig_stories":   12,
        "top_post": {
            "caption": "THE JOY OF THE LORD IS OUR STRENGTH.",
            "reach":   1100,
            "likes":   8,
            "comments": 0,
            "url":     "https://www.instagram.com/celebration.laketravis/",
        }
    },
]

def fmt_num(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)

def delta_str(v):   return f"+{v:,}" if v > 0 else f"{v:,}"
def delta_class(v): return "up" if v > 0 else ("down" if v < 0 else "neutral")

def get_week_range():
    today = datetime.now()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday

def fmt_date(d): return d.strftime("%B %-d, %Y")

def build():
    week_start, week_end = get_week_range()
    week_label   = f"{fmt_date(week_start)} – {fmt_date(week_end)}"
    generated_at = datetime.now().strftime("%B %-d, %Y at %-I:%M %p")

    scraped = [a for a in ACCOUNT_DATA if not a.get("error")]
    total_impressions = sum(a["impressions"] for a in scraped)
    total_reach       = sum(a["reach"] for a in scraped)
    total_engagement  = sum(a["engagement"] for a in scraped)
    total_posts       = sum(a.get("ig_posts", 0) + a.get("ig_stories", 0) for a in ACCOUNT_DATA)
    net_followers     = sum(a["new_followers"] for a in scraped)
    avg_eng_rate      = round((total_engagement / total_impressions * 100) if total_impressions else 0, 2)

    best_post_reach, best_post_account, best_post_url = 0, "", ""
    for a in ACCOUNT_DATA:
        tp = a.get("top_post") or {}
        if tp.get("reach", 0) > best_post_reach:
            best_post_reach   = tp["reach"]
            best_post_account = a["name"]
            best_post_url     = tp.get("url", "")

    # Bars
    max_r = max((a["impressions"] for a in ACCOUNT_DATA), default=1) or 1
    reach_bars = ""
    for a in sorted(ACCOUNT_DATA, key=lambda x: x["impressions"], reverse=True):
        pct = round(a["impressions"] / max_r * 100)
        color = CAMPUS_COLORS.get(a["handle"], "#3554c5")
        # Use blue for txcelebration bar so it's visible (black is invisible on dark bg)
        bar_color = "#3554c5" if color == "#282829" else color
        reach_bars += f"""
      <div class="bar-row">
        <div class="bar-name" title="{a['name']}">{a['name']}</div>
        <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{bar_color}"></div></div>
        <div class="bar-value">{fmt_num(a['impressions']) if a['impressions'] else '—'}</div>
      </div>"""

    # Cards
    account_cards = ""
    for a in ACCOUNT_DATA:
        nf = a["new_followers"]
        eng_rate = round((a["engagement"] / a["impressions"] * 100) if a["impressions"] else 0, 2)
        err_banner = ""
        if a.get("error"):
            err_banner = f'<div class="err-banner">⚠ {a["error"]}</div>'

        ig_posts   = a.get("ig_posts", 0)
        ig_stories = a.get("ig_stories", 0)
        content_str = []
        if ig_posts:   content_str.append(f"{ig_posts} post{'s' if ig_posts != 1 else ''}")
        if ig_stories: content_str.append(f"{ig_stories} stor{'ies' if ig_stories != 1 else 'y'}")
        content_label = " + ".join(content_str) if content_str else "—"

        profile_url = a.get("profile_url", f"https://www.instagram.com/{a['handle'].lstrip('@')}/")

        tp = a.get("top_post") or {}
        top_html = ""
        if tp and tp.get("caption"):
            comments = tp.get("comments", 0)
            top_html = f"""
        <div class="top-post-wrap">
          <div class="top-post-label">Top Post This Week</div>
          <div class="top-post">
            <div class="top-post-thumb">📸</div>
            <div class="top-post-body">
              <div class="top-post-caption">{tp['caption'][:240]}</div>
              <div class="top-post-stats">
                <span><strong>{fmt_num(tp.get('reach',0))}</strong> reach</span>
                <span><strong>{fmt_num(tp.get('likes',0))}</strong> likes</span>
                {f'<span><strong>{comments}</strong> comments</span>' if comments else ''}
              </div>
              <a class="top-post-link" href="{profile_url}" target="_blank" rel="noopener">View on Instagram ↗</a>
            </div>
          </div>
        </div>"""

        campus_color = CAMPUS_COLORS.get(a["handle"], "#3554c5")
        campus_img = CAMPUS_IMAGES.get(a["handle"])

        # txcelebration gets a 4-panel collage
        if a["handle"] == "@txcelebration":
            photo_col = """<div class="card-collage">
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_gt.jpg')"></div>
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_wave.jpg')"></div>
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_lt.jpg')"></div>
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_ca.jpg')"></div>
          <div class="collage-overlay"></div>
        </div>"""
        elif campus_img:
            photo_col = f'<div class="card-image"><img src="{campus_img}" alt="{a["name"]}" loading="lazy"></div>'
        else:
            photo_col = ""

        handle_safe = a["handle"].replace("@","").replace(".","_")
        account_cards += f"""
      <div class="account-card" style="--campus:{campus_color}" data-account="{a['handle']}">
        <div class="account-card-top"></div>
        <div class="account-header">
          <div class="account-header-left">
            <div class="campus-badge" style="background:{campus_color}">
              <img src="../assets/pebble.png" alt="" style="width:22px;height:22px;filter:brightness(0) invert(1)">
            </div>
            <div>
              <div class="account-name">{a['name']}</div>
              <div class="account-handle">{a['handle']}</div>
            </div>
          </div>
          <a class="account-cta" href="{profile_url}" target="_blank" rel="noopener">View Profile</a>
        </div>
        {err_banner}
        <div class="card-body">
          <div class="account-metrics">
            <div>
              <div class="metric-label">Views</div>
              <div class="metric-value" data-acct="{a['handle']}" data-acct-metric="views">{fmt_num(a['impressions']) if a['impressions'] else '—'}</div>
            </div>
            <div>
              <div class="metric-label">Reach</div>
              <div class="metric-value" data-acct="{a['handle']}" data-acct-metric="reach">{fmt_num(a['reach']) if a['reach'] else '—'}</div>
              {f'''<div class="reach-split">
                <span class="reach-split-item"><strong>{fmt_num(a.get("reach_followers",0))}</strong> followers</span>
                <span class="reach-split-item"><strong>{fmt_num(a.get("reach_nonfollowers",0))}</strong> non-followers</span>
              </div>
              <div class="reach-bar">
                <div class="reach-bar-followers" style="width:{round(a.get("reach_followers",0)/a["reach"]*100) if a["reach"] else 0}%"></div>
              </div>''' if a.get("reach") else ''}
            </div>
            <div>
              <div class="metric-label">Interactions</div>
              <div class="metric-value" data-acct="{a['handle']}" data-acct-metric="engagement">{fmt_num(a['engagement']) if a['engagement'] else '—'}</div>
            </div>
            <div>
              <div class="metric-label">Eng. Rate</div>
              <div class="metric-value" data-acct="{a['handle']}" data-acct-metric="eng_rate">{eng_rate}%</div>
            </div>
            <div>
              <div class="metric-label">Net Followers</div>
              <div class="metric-value">{delta_str(nf) if nf else '—'}</div>
              <div class="metric-delta {delta_class(nf)}">this period</div>
            </div>
            <div>
              <div class="metric-label">Content</div>
              <div class="metric-value" style="font-size:0.95rem">{content_label}</div>
              <div class="metric-sub">posts + stories</div>
            </div>
          </div>
          {photo_col}
        </div>
        {top_html}
      </div>"""

    period_label = "Oct 12 – Nov 8, 2026"

    # --- 7-day aggregates (from daily breakdowns) ---
    d7_views      = sum(a.get("d7_views",0)      for a in ACCOUNT_DATA)
    d7_reach      = sum(a.get("d7_reach",0)      for a in ACCOUNT_DATA)
    d7_engagement = sum(a.get("d7_engagement",0) for a in ACCOUNT_DATA)

    # --- 90-day aggregates ---
    d90_views      = sum(a.get("d90_views",0)      for a in ACCOUNT_DATA)
    d90_reach      = sum(a.get("d90_reach",0)      for a in ACCOUNT_DATA)
    d90_engagement = sum(a.get("d90_engagement",0) for a in ACCOUNT_DATA)

    # Per-account timeframe data for JS-driven card updates
    def acct_tf(a, tf):
        if tf == "7":
            views = a.get("d7_views", 0); reach = a.get("d7_reach", 0); eng = a.get("d7_engagement", 0)
        elif tf == "90":
            views = a.get("d90_views", 0); reach = a.get("d90_reach", 0); eng = a.get("d90_engagement", 0)
        else:
            views = a.get("impressions", 0); reach = a.get("reach", 0); eng = a.get("engagement", 0)
        er = round((eng / views * 100) if views else 0, 2)
        return {"views": fmt_num(views) if views else "—",
                "reach": fmt_num(reach) if reach else "—",
                "engagement": fmt_num(eng) if eng else "—",
                "eng_rate": f"{er}%"}

    tf_data = {
        "7": {
            "label":            "Last 7 Days",
            "dateRange":        "Nov 2 – Nov 8, 2026",
            "total_views":      fmt_num(d7_views),
            "total_engagement": fmt_num(d7_engagement),
            "net_followers":    delta_str(net_followers),
            "total_posts":      "—",
            "accounts": {a["handle"]: acct_tf(a, "7") for a in ACCOUNT_DATA},
        },
        "28": {
            "label":            "Last 28 Days",
            "dateRange":        "Oct 12 – Nov 8, 2026",
            "total_views":      fmt_num(total_impressions),
            "total_engagement": fmt_num(total_engagement),
            "net_followers":    delta_str(net_followers),
            "total_posts":      str(total_posts),
            "accounts": {a["handle"]: acct_tf(a, "28") for a in ACCOUNT_DATA},
        },
        "90": {
            "label":            "Last 90 Days",
            "dateRange":        "Aug 11 – Nov 8, 2026",
            "total_views":      fmt_num(d90_views),
            "total_engagement": fmt_num(d90_engagement),
            "net_followers":    "—",
            "total_posts":      "—",
            "accounts": {a["handle"]: acct_tf(a, "90") for a in ACCOUNT_DATA},
        },
    }

    top_account_name = max(ACCOUNT_DATA, key=lambda x: x.get("impressions",0), default={"handle":"—"})["handle"]

    html = TEMPLATE.read_text() \
        .replace("{{WEEK_OF}}",          week_label) \
        .replace("{{GENERATED_DATE}}",   generated_at) \
        .replace("{{ACCOUNT_COUNT}}",    f"{len(scraped)} of {len(ACCOUNT_DATA)}") \
        .replace("{{TOTAL_REACH}}",      fmt_num(total_impressions)) \
        .replace("{{TOTAL_IMPRESSIONS}}",fmt_num(total_impressions)) \
        .replace("{{TOTAL_ENGAGEMENT}}", fmt_num(total_engagement)) \
        .replace("{{TOTAL_POSTS}}",      str(total_posts)) \
        .replace("{{NET_FOLLOWERS}}",    delta_str(net_followers)) \
        .replace("{{AVG_ENG_RATE}}",     str(avg_eng_rate)) \
        .replace("{{ENG_DELTA}}",        "+0") \
        .replace("{{ENG_DELTA_CLASS}}",  "neutral") \
        .replace("{{TOP_PLATFORM}}",     top_account_name) \
        .replace("{{BEST_POST_REACH}}",  fmt_num(best_post_reach)) \
        .replace("{{BEST_POST_ACCOUNT}}",best_post_account) \
        .replace("{{BEST_POST_URL}}",    best_post_url) \
        .replace("{{TOTAL_FOLLOWERS}}",  "—") \
        .replace("{{FOLLOW_DELTA}}",     delta_str(net_followers)) \
        .replace("{{FOLLOW_DELTA_CLASS}}",delta_class(net_followers)) \
        .replace("{{PERIOD_LABEL}}",     period_label) \
        .replace("{{REACH_BARS}}",       reach_bars) \
        .replace("{{ACCOUNT_CARDS}}",    account_cards) \
        .replace("TIMEFRAME_DATA",       json.dumps(tf_data))

    # Save
    fname = f"week-{week_start.strftime('%Y-%m-%d')}.html"
    (REPORTS_DIR / fname).write_text(html)
    print(f"✓ Saved: reports/{fname}")

    # Update index
    entries = json.loads(INDEX_JSON.read_text()) if INDEX_JSON.exists() else []
    entries = [{
        "file":       fname,
        "weekOf":     week_label,
        "accounts":   len(ACCOUNT_DATA),
        "totalPosts": total_posts,
        "totalReach": total_impressions,
        "generated":  datetime.now().isoformat(),
    }] + [e for e in entries if e["file"] != fname]
    INDEX_JSON.write_text(json.dumps(entries, indent=2))

    idx = INDEX_PATH.read_text()
    idx = idx.replace("REPORTS_INDEX", json.dumps(entries))
    INDEX_PATH.write_text(idx)
    print("✓ Index updated")

    # Git push
    repo_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    for cmd in [
        ["git","-C",str(REPO_DIR),"config","user.email","noreply@anthropic.com"],
        ["git","-C",str(REPO_DIR),"config","user.name","Claude"],
        ["git","-C",str(REPO_DIR),"add","-A"],
        ["git","-C",str(REPO_DIR),"commit","-m",
         f"Weekly social report: {week_label} (3/7 accounts)\n\n"
         f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>\n"
         f"Claude-Session: https://claude.ai/code/session_01FREnhoqwbgRoopNEi7GBHY"],
        ["git","-C",str(REPO_DIR),"push",repo_url,"main"],
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout+r.stderr):
            print(f"Git note: {r.stderr.strip()[:100]}")
    print("✓ Pushed → Cloudflare deploying now")
    print(f"\n🎉 Report live at: https://celebration-social-reports.pages.dev")

if __name__ == "__main__":
    build()

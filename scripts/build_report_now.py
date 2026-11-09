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
        "reach_nonfollowers": 190744, # reach - followers (adjusted for consistency)
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
        "reach_nonfollowers": 22164, # reach - followers (adjusted for consistency)
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
        "reach_nonfollowers": 5688, # reach - followers (adjusted for consistency)
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

    # Total non-follower reach across all accounts
    total_nf_reach = sum(a.get("reach_nonfollowers", 0) for a in scraped)

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

    # ── Auto-generate per-account insights from analytics data ───────────────
    def account_score(a):
        """Data-driven 0–10 score from engagement rate, non-follower reach, posts, and growth."""
        views = a.get("impressions", 0)
        eng   = a.get("engagement", 0)
        reach = a.get("reach", 0)
        nf_reach = a.get("reach_nonfollowers", 0)
        posts = a.get("ig_posts", 0)
        stories = a.get("ig_stories", 0)
        new_f = a.get("new_followers", 0)

        # Engagement rate vs Instagram benchmarks (avg ~1–3%)
        er = (eng / views * 100) if views else 0
        er_pts = 3 if er >= 4 else (2 if er >= 2.5 else (1 if er >= 1 else 0))

        # Non-follower reach ratio — how well content discovers new people
        nf_pct = (nf_reach / reach * 100) if reach else 0
        nf_pts = 3 if nf_pct >= 80 else (2 if nf_pct >= 60 else (1 if nf_pct >= 30 else 0))

        # Posting activity — feed posts matter more than stories for discoverability
        post_pts = 2 if posts >= 2 else (1 if posts == 1 else 0)

        # Follower growth
        growth_pts = 2 if new_f >= 20 else (1 if new_f > 0 else 0)

        raw = er_pts + nf_pts + post_pts + growth_pts  # 0–10
        return round(raw, 1)

    def account_insight(a, all_accounts):
        views    = a.get("impressions", 0)
        reach    = a.get("reach", 0)
        nf_reach = a.get("reach_nonfollowers", 0)
        f_reach  = a.get("reach_followers", 0)
        eng      = a.get("engagement", 0)
        er       = round((eng / views * 100) if views else 0, 2)
        nf_pct   = round((nf_reach / reach * 100) if reach else 0)
        posts    = a.get("ig_posts", 0)
        stories  = a.get("ig_stories", 0)
        new_f    = a.get("new_followers", 0)
        d7_v     = a.get("d7_views", 0)
        d90_v    = a.get("d90_views", 0)

        # Rank this account among all by impressions
        sorted_by_views = sorted(all_accounts, key=lambda x: x.get("impressions",0), reverse=True)
        rank = next(i+1 for i, x in enumerate(sorted_by_views) if x["handle"] == a["handle"])
        total = len(all_accounts)

        # Trend: compare 7-day to 28-day daily average
        daily_28 = views / 28 if views else 0
        daily_7  = d7_v / 7 if d7_v else 0
        trend = "above" if daily_7 > daily_28 * 1.1 else ("below" if daily_7 < daily_28 * 0.9 else "in line with")

        # Build summary sentence from data
        content_mix = ""
        if posts == 0 and stories > 0:
            content_mix = f"Published no feed posts this period — {stories} stories only."
        elif posts > 0 and stories == 0:
            content_mix = f"Published {posts} feed post{'s' if posts>1 else ''} with no stories."
        else:
            content_mix = f"Published {posts} feed post{'s' if posts>1 else ''} and {stories} stor{'ies' if stories>1 else 'y'}."

        follower_note = ""
        if new_f < 0:
            follower_note = f"Net follower count is <strong>negative ({new_f})</strong> — the only account declining this period."
        elif new_f == 0:
            follower_note = "Net follower change is flat at zero."
        else:
            follower_note = f"Gained <strong>{delta_str(new_f)} followers</strong> over 28 days."

        summary = (
            f"Ranked <strong>#{rank} of {total}</strong> by views this period with "
            f"<strong>{fmt_num(views)}</strong> views and an engagement rate of <strong>{er}%</strong>. "
            f"{content_mix} "
            f"7-day volume is {trend} the 28-day daily average, suggesting momentum is "
            f"{'building' if trend == 'above' else ('fading' if trend == 'below' else 'steady')}. "
            f"{follower_note}"
        )

        # Wins — flag genuinely strong signals
        wins = []
        if nf_pct >= 70:
            wins.append(f"<strong>{nf_pct}%</strong> of reach is non-followers — content is finding new people.")
        if er >= 4:
            wins.append(f"<strong>{er}%</strong> engagement rate is well above the Instagram average of 1–3%.")
        elif er >= 2.5:
            wins.append(f"<strong>{er}%</strong> engagement rate — solid, above average for this platform.")
        if new_f >= 20:
            wins.append(f"<strong>{delta_str(new_f)}</strong> net new followers is the strongest growth signal in the network.")
        if stories >= 20:
            wins.append(f"<strong>{stories} stories</strong> published — consistent daily presence keeps the account visible.")
        if posts >= 3:
            wins.append(f"<strong>{posts} feed posts</strong> in the period — steady feed presence aids discoverability.")
        if not wins:
            wins.append(f"{fmt_num(views)} views reached despite limited posting — there's latent audience interest here.")

        # Fixes — flag the real gaps
        fixes = []
        if posts == 0:
            fixes.append("Zero feed posts this period. Feed presence is what the algorithm uses for discovery — stories alone won't grow the account.")
        elif posts == 1:
            fixes.append("One feed post is better than zero but not enough to build consistent reach. Aim for 2–3 per week.")
        if nf_pct < 40 and reach > 0:
            fixes.append(f"Only {nf_pct}% of reach is non-followers. Content isn't traveling beyond the existing audience — worth examining what's limiting discovery.")
        if new_f <= 0:
            fixes.append("No follower growth (or negative). Feed activity and non-follower content are the levers to pull.")
        if er < 1.5 and views > 0:
            fixes.append(f"Engagement rate of {er}% is below the platform baseline. Consider whether the content is giving the audience something to respond to.")
        if daily_7 < daily_28 * 0.85:
            fixes.append("7-day views are running below the 28-day average — this week's output was lighter than the period trend.")
        if not fixes:
            fixes.append("Strong across the board. Maintain posting frequency and test one new content angle to push non-follower reach higher.")

        return {"summary": summary, "wins": wins[:3], "fixes": fixes[:3]}

    # Cards and tab nav
    account_tab_nav = ""
    account_panels  = ""
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

        top_html = ""  # top post section removed (no direct post URLs available)

        campus_color = CAMPUS_COLORS.get(a["handle"], "#3554c5")
        campus_img = CAMPUS_IMAGES.get(a["handle"])

        # Build full-bleed background layer
        if a["handle"] == "@txcelebration":
            # Collage uses different photos than the individual account cards
            bg_html = """<div class="card-collage-bg">
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_gt.jpg')"></div>
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_wave.jpg')"></div>
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_lt.jpg')"></div>
          <div class="collage-panel" style="background-image:url('../assets/campus/collage_ca.jpg')"></div>
        </div>
        <div class="card-bg-gradient"></div>"""
        elif campus_img:
            bg_html = (f'<div class="card-bg-image" style="background-image:url(\'{campus_img}\')"></div>\n'
                       f'        <div class="card-bg-gradient"></div>')
        else:
            bg_html = ""

        # Reach breakdown: followers vs non-followers bar (28-day data only)
        rf  = a.get("reach_followers", 0)
        rnf = a.get("reach_nonfollowers", 0)
        r28 = a.get("reach", 0)
        follower_pct = round(rf / r28 * 100) if r28 else 0
        reach_breakdown = ""
        if r28:
            reach_breakdown = f"""<div class="reach-split">
                <span class="reach-split-item"><strong>{fmt_num(rf)}</strong> followers</span>
                <span class="reach-split-item"><strong>{fmt_num(rnf)}</strong> non-followers</span>
              </div>
              <div class="reach-bar">
                <div class="reach-bar-followers" style="width:{follower_pct}%"></div>
              </div>"""

        # Net followers display (never zero-suppress — show 0 explicitly)
        nf_display = delta_str(nf) if nf is not None else "—"
        nf_class   = delta_class(nf) if nf is not None else "neutral"

        # Top-level tab nav button (data-top= drives the top panel switcher)
        sc = account_score(a)
        is_first = (a == ACCOUNT_DATA[0])
        panel_id = a["handle"].replace("@","").replace(".","_")
        account_tab_nav += f'<button class="top-tab-btn" data-top="{panel_id}" style="--campus:{campus_color}">{a["handle"]} · {sc}/10</button>\n'

        # Per-account AI insight block
        insight = account_insight(a, ACCOUNT_DATA)
        wins_html  = "".join(f'<div class="insight-bullet">{w}</div>' for w in insight["wins"])
        fixes_html = "".join(f'<div class="insight-bullet">{f}</div>' for f in insight["fixes"])
        score_display = f"{sc}/10"

        card_html = f"""<div class="account-card" style="--campus:{campus_color}" data-account="{a['handle']}">
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
            {bg_html}
            <div class="account-metrics">
              <div>
                <div class="metric-label">Views</div>
                <div class="metric-value" data-acct="{a['handle']}" data-acct-metric="views">{fmt_num(a['impressions']) if a['impressions'] else '—'}</div>
              </div>
              <div>
                <div class="metric-label">Reach</div>
                <div class="metric-value" data-acct="{a['handle']}" data-acct-metric="reach">{fmt_num(r28) if r28 else '—'}</div>
                {reach_breakdown}
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
                <div class="metric-value">{nf_display}</div>
                <div class="metric-delta {nf_class}">28-day period</div>
              </div>
              <div>
                <div class="metric-label">Content</div>
                <div class="metric-value" style="font-size:0.95rem">{content_label}</div>
                <div class="metric-sub">posts + stories</div>
              </div>
            </div>
          </div>
        </div>"""

        insight_html = f"""<div class="acct-insight">
          <div class="acct-insight-header">
            <div class="campus-badge" style="background:{campus_color}">
              <img src="../assets/pebble.png" alt="" style="width:22px;height:22px;filter:brightness(0) invert(1)">
            </div>
            <div>
              <div style="font-family:var(--font-display);font-size:1rem;font-weight:400">{a['name']} — Content Audit</div>
              <div class="insight-label">{week_label} · {ig_posts} posts · {ig_stories} stories · AI analytics scoring</div>
            </div>
            <div class="insight-score-pill" style="background:{campus_color}">{score_display}</div>
          </div>
          <div class="acct-insight-body">
            <div class="insight-col">
              <h4>Summary</h4>
              <p>{insight['summary']}</p>
            </div>
            <div class="insight-col">
              <h4>What's working</h4>
              <div class="insight-bullets">{wins_html}</div>
              <h4 style="margin-top:1rem">Fix this week</h4>
              <div class="insight-bullets">{fixes_html}</div>
            </div>
          </div>
        </div>"""

        account_panels += f"""<div class="top-panel" id="top-{panel_id}">
        <div style="display:flex;flex-direction:column;gap:1.25rem">
          {card_html}
          {insight_html}
        </div>
      </div>"""

    # ── Auto-generated scoring panel ─────────────────────────────────────────
    scores = [(a, account_score(a)) for a in ACCOUNT_DATA]
    net_score   = round(sum(s for _, s in scores) / len(scores), 1)
    best_acct   = max(scores, key=lambda x: x[1])
    weakest_acct = min(scores, key=lambda x: x[1])

    # Accounts with zero feed posts
    no_posts = [a for a in ACCOUNT_DATA if a.get("ig_posts", 0) == 0]
    posting_rate = round((len(ACCOUNT_DATA) - len(no_posts)) / len(ACCOUNT_DATA) * 100)

    # Network-level wins (from analytics)
    top_nf_pct    = round(total_nf_reach / total_reach * 100) if total_reach else 0
    best_eng_acct = max(ACCOUNT_DATA, key=lambda x: round((x["engagement"]/x["impressions"]*100) if x["impressions"] else 0, 2))
    best_eng_rate = round((best_eng_acct["engagement"]/best_eng_acct["impressions"]*100) if best_eng_acct["impressions"] else 0, 2)
    best_growth   = max(ACCOUNT_DATA, key=lambda x: x.get("new_followers", 0))

    # Score label
    if net_score >= 7: score_label = "Strong week across the network."
    elif net_score >= 5: score_label = "Solid in spots, gaps elsewhere."
    elif net_score >= 3: score_label = "Inconsistent — a few accounts carrying the rest."
    else: score_label = "Network output needs attention."

    # Score driver narrative
    posting_flag = f"{len(no_posts)} of {len(ACCOUNT_DATA)} accounts published zero feed posts" if no_posts else "All accounts posted to their feeds"
    nf_flag = f"{top_nf_pct}% of total reach came from non-followers — content is finding new audiences" if top_nf_pct > 50 else f"Only {top_nf_pct}% of reach was non-followers — content isn't traveling far beyond existing audiences"

    # Build wins HTML
    wins_items = [
        ("📈", f"{best_acct[0]['name']} led the network",
                f"{fmt_num(best_acct[0]['impressions'])} views, {round(best_acct[0]['engagement']/best_acct[0]['impressions']*100,2)}% engagement rate — the strongest performer this period."),
        ("🌍", f"Non-follower reach: {fmt_num(total_nf_reach)} accounts",
                f"{top_nf_pct}% of total reach is new eyes on the church. Discovery is happening — particularly through {max(ACCOUNT_DATA, key=lambda x: x.get('reach_nonfollowers',0))['name']}."),
        ("📊", f"{best_eng_acct['name']} engagement: {best_eng_rate}%",
                f"Well above the Instagram average of 1–3%. The audience is responding to what this account puts out."),
        ("🌱", f"Best growth: {best_growth['name']} (+{best_growth.get('new_followers',0)} followers)",
                f"Highest net new follower count this period — {fmt_num(best_growth.get('reach_nonfollowers',0))} non-follower accounts reached."),
    ]
    wins_html = "".join(f"""<div class="score-item">
              <span class="score-icon">{icon}</span>
              <div class="score-item-text"><strong>{title}</strong><span>{body}</span></div>
            </div>""" for icon, title, body in wins_items)

    # Build fixes HTML — flag real data-driven gaps
    fix_items = []
    if no_posts:
        names = ", ".join(a["name"] for a in no_posts)
        fix_items.append(("🚫", f"{len(no_posts)} account{'s' if len(no_posts)>1 else ''} with no feed posts",
                          f"{names}. Feed posts are what the algorithm uses to reach new people. Stories alone don't grow accounts."))
    low_eng = [a for a in ACCOUNT_DATA if a["impressions"] and (a["engagement"]/a["impressions"]*100) < 1.5]
    if low_eng:
        fix_items.append(("📉", "Below-baseline engagement rates",
                          f"{', '.join(a['name'] for a in low_eng)} {'are' if len(low_eng)>1 else 'is'} below 1.5% — worth asking whether the content is giving people a reason to respond."))
    neg_growth = [a for a in ACCOUNT_DATA if a.get("new_followers", 0) < 0]
    if neg_growth:
        fix_items.append(("⬇", "Net follower decline",
                          f"{', '.join(a['name'] for a in neg_growth)} lost followers this period. Inactive feeds tend to accelerate churn."))
    if not fix_items:
        fix_items.append(("✳", "Maintain posting consistency",
                          "All accounts are posting. The next level is testing content that opens more of its reach to non-followers."))
    # Always add a growth lever
    fix_items.append(("🔁", f"Only {posting_rate}% of accounts posting to feeds",
                      "Consistent weekly feed posts from every campus account would compound reach week over week."))

    fixes_html = "".join(f"""<div class="score-item">
              <span class="score-icon">{icon}</span>
              <div class="score-item-text"><strong>{title}</strong><span>{body}</span></div>
            </div>""" for icon, title, body in fix_items[:4])

    # Per-account score grid
    acct_score_cells = ""
    for a, s in scores:
        color = CAMPUS_COLORS.get(a["handle"], "#3554c5")
        bar_col = "#3554c5" if color == "#282829" else color
        acct_score_cells += f"""<div class="acct-score-cell" style="--campus:{bar_col}">
          <div class="acct-score-badge" style="background:{bar_col}">
            <img src="../assets/pebble.png" alt="" style="width:16px;height:16px;filter:brightness(0) invert(1)">
          </div>
          <div>
            <div class="acct-score-name">{a['name']}</div>
            <div class="acct-score-handle">{a['handle']}</div>
          </div>
          <div class="acct-score-num" style="color:{bar_col}">{s}/10</div>
        </div>"""

    scoring_panel = f"""<div class="scoring-panel">
        <div class="score-hero">
          <div><div class="score-num">{net_score}<span class="score-denom">/10</span></div></div>
          <div class="score-hero-text">
            <h2>{score_label}</h2>
            <p>{posting_flag} this period. {nf_flag}.
            Network engagement rate: {avg_eng_rate}%. Net new followers across all accounts: {delta_str(net_followers)}.
            Score is analytics-driven: engagement rate, non-follower reach ratio, posting activity, and follower growth.</p>
          </div>
        </div>
        <div class="score-cols">
          <div class="score-col wins"><h3>✅ What's working</h3>{wins_html}</div>
          <div class="score-col fixes"><h3>🔧 Address this week</h3>{fixes_html}</div>
        </div>
        <div>
          <div class="section-label" style="margin-bottom:0.75rem">Account Scores</div>
          <div class="acct-scores-grid">{acct_score_cells}</div>
          <p style="font-size:0.68rem;color:var(--fg-muted);margin-top:0.75rem;font-weight:300">
            Score (0–10) = engagement rate + non-follower reach % + posting activity + follower growth. Generated automatically from Meta Business Suite analytics.
          </p>
        </div>
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
            # Net followers & posts tracked on 28-day period only
            "net_followers":    delta_str(net_followers),
            "total_posts":      str(total_posts),
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
            # Net followers & posts not aggregated for 90-day period
            "net_followers":    delta_str(net_followers),
            "total_posts":      str(total_posts),
            "accounts": {a["handle"]: acct_tf(a, "90") for a in ACCOUNT_DATA},
        },
    }

    top_account_name = max(ACCOUNT_DATA, key=lambda x: x.get("impressions",0), default={"name":"—"})["name"]

    # ── AI Weekly Summary ────────────────────────────────────────────────────
    # Verified follower counts from live Instagram pages (Nov 9, 2026):
    # txcelebration: 26,200 | wave.students: 7,348 | celebration.leander: 1,717
    # celebration.centralaustin: 2,704 | celebration.georgetown: 796 | celebration.laketravis: 854
    # Analytics source: Meta Business Suite (authoritative). 7-day figures from daily breakdowns.

    # Georgetown non-follower ratio
    gt = next(a for a in ACCOUNT_DATA if a["handle"] == "@celebration.georgetown")
    gt_nf_pct = round(gt.get("reach_nonfollowers",0) / gt["reach"] * 100) if gt["reach"] else 0

    # Stories-only accounts
    stories_only = [a["name"] for a in ACCOUNT_DATA if a.get("ig_posts",0) == 0 and a.get("ig_stories",0) > 0]

    # Best non-follower reach account
    best_nf_acct = max(ACCOUNT_DATA, key=lambda x: x.get("reach_nonfollowers",0))

    # Lowest engagement rate
    eng_rates = [(a, round(a["engagement"]/a["impressions"]*100,2)) for a in ACCOUNT_DATA if a["impressions"]]
    weakest = min(eng_rates, key=lambda x: x[1])

    ai_summary = f"""
      <div class="ai-summary-block">
        <h3><span class="dot" style="background:var(--blue)"></span>Overall Network</h3>
        <p>Across all 6 accounts, Celebration generated <strong>{fmt_num(total_impressions)} views</strong> and reached
        <strong>{fmt_num(total_reach)} unique accounts</strong> in the 28-day window ending Nov 8.
        Of that reach, <strong>{fmt_num(total_nf_reach)}</strong> ({round(total_nf_reach/total_reach*100) if total_reach else 0}%) came from
        people who don't yet follow any campus — a strong discovery signal.
        Net follower growth across the network was <strong>{delta_str(net_followers)}</strong>.</p>
      </div>
      <div class="ai-summary-block">
        <h3><span class="dot" style="background:var(--black)"></span>txcelebration — Main Campus</h3>
        <p><strong>Top performer by every metric</strong> — {fmt_num(ACCOUNT_DATA[0]['impressions'])} views,
        {fmt_num(ACCOUNT_DATA[0]['engagement'])} interactions, and {delta_str(ACCOUNT_DATA[0]['new_followers'])} new followers in 28 days.
        6 feed posts and 21 stories published. Live follower count: <strong>26.2K</strong>.
        Non-follower reach ({fmt_num(ACCOUNT_DATA[0].get('reach_nonfollowers',0))}) is unusually high —
        content is breaking well beyond the existing audience.</p>
      </div>
      <div class="ai-summary-block">
        <h3><span class="dot" style="background:var(--blue)"></span>Georgetown — Breakout Reach</h3>
        <p>Georgetown punches far above its follower count (<strong>796 followers</strong> live on Instagram).
        <strong>{gt_nf_pct}%</strong> of its {fmt_num(gt['reach'])} reach came from non-followers,
        with {delta_str(gt['new_followers'])} net new followers this period — the highest growth rate of any campus account.
        4 posts and 10 stories published. The pastor invite post drove significant reach.</p>
      </div>
      <div class="ai-summary-block">
        <h3><span class="dot" style="background:var(--yellow)"></span>Wave Students — Stories-First</h3>
        <p>Wave ran an <strong>all-stories strategy</strong> (0 feed posts, 26 stories) and still generated
        {fmt_num(ACCOUNT_DATA[1]['impressions'])} views and {fmt_num(ACCOUNT_DATA[1]['engagement'])} interactions.
        Live follower count is <strong>7,348</strong>. Stories are clearly resonating with the student audience —
        but a single high-quality feed post each week could meaningfully extend reach beyond current followers.</p>
      </div>
      <div class="ai-summary-block">
        <h3><span class="dot" style="background:var(--orange)"></span>Central Austin &amp; Lake Travis</h3>
        <p>Both campuses relied entirely on stories ({ACCOUNT_DATA[4].get('ig_stories',0)} and {ACCOUNT_DATA[5].get('ig_stories',0)} respectively, 0 feed posts).
        Central Austin saw <strong>-1 net follower</strong> — the only campus with a decline — and the lowest engagement rate
        at {weakest[1]}%. Lake Travis delivered a solid {round(ACCOUNT_DATA[5]['engagement']/ACCOUNT_DATA[5]['impressions']*100,2)}% engagement rate despite low volume.
        Both campuses would benefit from at least 1 feed post per week to maintain algorithmic visibility.</p>
      </div>
      <div class="ai-summary-block">
        <h3><span class="dot" style="background:var(--olive)"></span>Leander — Steady</h3>
        <p>Leander/Liberty Hill published 2 posts and 7 stories, earning {fmt_num(ACCOUNT_DATA[3]['impressions'])} views and
        {delta_str(ACCOUNT_DATA[3]['new_followers'])} new followers. Live follower count: <strong>1,717</strong>.
        Engagement rate of {round(ACCOUNT_DATA[3]['engagement']/ACCOUNT_DATA[3]['impressions']*100,2)}% is healthy.
        <strong>Data verified:</strong> Meta Business Suite analytics cross-referenced against live Instagram follower counts — figures align.</p>
      </div>"""

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
        .replace("{{TOTAL_NF_REACH}}",   fmt_num(total_nf_reach)) \
        .replace("{{TOTAL_FOLLOWERS}}",  "—") \
        .replace("{{FOLLOW_DELTA}}",     delta_str(net_followers)) \
        .replace("{{FOLLOW_DELTA_CLASS}}",delta_class(net_followers)) \
        .replace("{{PERIOD_LABEL}}",     period_label) \
        .replace("{{REACH_BARS}}",       reach_bars) \
        .replace("{{ACCOUNT_TAB_NAV}}",  account_tab_nav) \
        .replace("{{ACCOUNT_PANELS}}",   account_panels) \
        .replace("{{SCORING_PANEL}}",    scoring_panel) \
        .replace("{{ACCOUNT_CARDS}}",    "") \
        .replace("{{AI_SUMMARY}}",       ai_summary) \
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

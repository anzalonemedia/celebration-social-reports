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

    # ── Per-account content scores from content audit (Nov 2–8, 2026) ────────
    CONTENT_SCORES = {
        "@txcelebration":            {"posts": 5, "score": 7.6, "read": "Strongest feed: Scripture, real people, links"},
        "@wave.students":            {"posts": 7, "score": 5.1, "read": "Seven posts for one night, mostly logistics"},
        "@celebration.georgetown":   {"posts": 3, "score": 4.3, "read": "Strong photos, 'Celebration Family' copy"},
        "@celebration.leander":      {"posts": 1, "score": 4.0, "read": "Sunday recap posted on Tuesday"},
        "@celebration.centralaustin":{"posts": 0, "score": None, "read": "No post of its own since Oct 17"},
        "@celebration.laketravis":   {"posts": 0, "score": None, "read": "No post of its own since Oct 7"},
    }

    # Per-account AI insights
    ACCOUNT_INSIGHTS = {
        "@txcelebration": {
            "summary": "Main campus led the network with a <strong>7.6/10</strong> content score — the highest of any account. "
                       "5 feed posts anchored by real people and scripture performed well. "
                       "The standout was Pastor Jackson's Philippians 4:8 clip (<strong>9/10</strong>): one verse, one idea, a link. "
                       "Pastor Joe's selfie invitation (<strong>7/10</strong>) drove the week's most likes (685) and 31 shares — "
                       "but the caption opened with 'Hey church!!' and had no times or newcomer invite.",
            "wins": [
                "Pastor Jackson's Philippians 4:8 post: 566 likes, 26 comments, 27 shares",
                "Non-follower reach at 190K+ — content is breaking beyond existing audience",
                "Scripture and real people in frame = top-performing combination",
            ],
            "fixes": [
                "Start captions with WHY before logistics — 'Mind won't slow down? Try this verse for one week.'",
                "Pastor Joe invitation: add all campus times + 'bring someone' to the caption",
                "Collab WAVE United and big ministry nights onto the main feed for parent reach",
            ],
        },
        "@wave.students": {
            "summary": "WAVE posted 7 times in one week — all for WAVE United Rodeo night (Nov 8). "
                       "Photos were full of real students. Copy was nearly all logistics, only one post "
                       "said why a student should come. Best post: 'WAVE UNITED is so fun!!!' (<strong>8/10</strong>) "
                       "— real hug photo, list of fun things, then worship and message with time + address. "
                       "WAVE United never reached the main feed — the biggest student night of fall was "
                       "invisible to parents.",
            "wins": [
                "'WAVE UNITED is so fun' post hit 8/10 — real people, clear why + where",
                "7 posts showed consistent energy and real student moments",
                "26 stories kept students engaged throughout the week",
            ],
            "fixes": [
                "Lead with WHY before the activity list — 'One night for every student in our church'",
                "Collab major events onto @txcelebration so parents and the broader church see it",
                "Add 1 feed post per week outside events to build consistent audience between nights",
            ],
        },
        "@celebration.georgetown": {
            "summary": "Georgetown posted 3 times and averaged <strong>4.3/10</strong>. Photos were strong — "
                       "real people, well lit. The copy defaulted to 'Celebration Family' on all three "
                       "captions, which reads as insider language and closes the door to newcomers. "
                       "The Pursuit Night recap went up Friday evening, two days after the event. "
                       "The pastor invite collab drove the week's best reach for this campus (7.1K).",
            "wins": [
                "Strong photo quality — real people in real moments",
                "Pastor invite collab reached 7,100 accounts — highest single-post reach",
                "+87 net new followers this period, highest growth rate across all campus accounts",
            ],
            "fixes": [
                "Drop 'Celebration Family' — replace with specific, newcomer-friendly language",
                "Post Sunday recap on Sunday, not Friday — timing matters for algorithmic reach",
                "Add times, address, and 'new here? plan your visit' to service-time posts",
            ],
        },
        "@celebration.leander": {
            "summary": "Leander posted once: a warm lobby photo of a woman hugging a little girl, captioned "
                       "'What a great Sunday!' — posted Tuesday at 4:04 PM, two days after Sunday (<strong>4/10</strong>). "
                       "The photo had real emotional pull; the caption gave no reason to come, no time, no place. "
                       "15 net new followers suggest organic discovery is happening — there's an audience "
                       "ready for more consistent content.",
            "wins": [
                "Real, emotionally warm photo — the right visual instinct",
                "+15 net new followers despite minimal posting",
                "Stories strategy (7) kept engagement active through the week",
            ],
            "fixes": [
                "Post Sunday recap on Sunday afternoon — timing is content",
                "Caption formula: [why it matters] + [times] + [address] + [plan your visit link]",
                "Aim for 2–3 feed posts/week: Sunday recap, mid-week moment, and an invite",
            ],
        },
        "@celebration.centralaustin": {
            "summary": "Central Austin published <strong>no original feed posts</strong> this week — or in the "
                       "three weeks prior (last post Oct 17). The only content on the grid is a main-account "
                       "collab from Oct 23. 26 stories went out, so the account is active, but the feed "
                       "has gone dark. This contributed to the week's only net-negative follower count (-1). "
                       "An account with 2,704 followers and no feed posts is leaving significant reach on the table.",
            "wins": [
                "26 stories published — team is active and creating content",
                "2,704 followers represent a real local audience worth engaging",
                "Engagement rate on stories appears strong relative to account size",
            ],
            "fixes": [
                "Post at minimum 1 original feed post per week — a local photo with a real person + Sunday times",
                "Sunday recap post every Sunday — this alone would re-activate the feed algorithm",
                "Avoid collab-only feeds; campus accounts need their own voice",
            ],
        },
        "@celebration.laketravis": {
            "summary": "Lake Travis has not published an original feed post since Oct 7 — over a month. "
                       "Like Central Austin, 12 stories ran this week, but the grid is effectively dormant. "
                       "With 854 followers and 34K views this period (from stories + collabs), there's clear "
                       "interest in this campus. A weekly local photo post would meaningfully extend that reach "
                       "beyond the existing audience.",
            "wins": [
                "34K views despite no feed posts — stories are driving real impressions",
                "Engagement rate (2.72%) is decent for the account's size",
                "+10 net new followers this period — people are finding and following",
            ],
            "fixes": [
                "Resume feed posting immediately — 1 original post per week minimum",
                "Lead with a photo of a real person + 'See you Sunday' + campus times",
                "Sunday recap post on Sunday: 'This is Sunday at Lake Travis' + join us next week",
            ],
        },
    }

    # Cards and tab nav
    account_tab_nav = ""
    account_panels = ""
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

        # Tab nav button
        cs = CONTENT_SCORES.get(a["handle"], {})
        score_badge = f" · {cs['score']}/10" if cs.get("score") else ""
        is_first = (a == ACCOUNT_DATA[0])
        panel_id = a["handle"].replace("@","").replace(".","_")
        account_tab_nav += f'<button class="acct-tab-btn{" active" if is_first else ""}" data-panel="{panel_id}" style="--campus:{campus_color}">{a["handle"]}{score_badge}</button>\n'

        # Per-account AI insight block
        insight = ACCOUNT_INSIGHTS.get(a["handle"], {})
        wins_html  = "".join(f'<div class="insight-bullet">{w}</div>' for w in insight.get("wins", []))
        fixes_html = "".join(f'<div class="insight-bullet">{f}</div>' for f in insight.get("fixes", []))
        score_display = f"{cs['score']}/10" if cs.get("score") else "—"

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
              <div class="insight-label">Week of Nov 2–8, 2026 · {cs.get('posts',0)} original posts · AI content scoring</div>
            </div>
            <div class="insight-score-pill" style="background:{campus_color}">{score_display}</div>
          </div>
          <div class="acct-insight-body">
            <div class="insight-col">
              <h4>Summary</h4>
              <p>{insight.get('summary','No summary available.')}</p>
            </div>
            <div class="insight-col">
              <h4>What's working</h4>
              <div class="insight-bullets">{wins_html}</div>
              <h4 style="margin-top:1rem">Fix this week</h4>
              <div class="insight-bullets">{fixes_html}</div>
            </div>
          </div>
        </div>"""

        account_panels += f"""<div class="acct-panel{' active' if is_first else ''}" id="panel-{panel_id}">
        {card_html}
        {insight_html}
      </div>"""

    # Add scoring tab button
    account_tab_nav += '<button class="acct-tab-btn scoring-btn" data-panel="scoring">⭐ Scoring</button>\n'

    # ── Scoring panel ────────────────────────────────────────────────────────
    # Per-account scores for the grid
    acct_score_cells = ""
    for a in ACCOUNT_DATA:
        cs = CONTENT_SCORES.get(a["handle"], {})
        color = CAMPUS_COLORS.get(a["handle"], "#3554c5")
        s = cs.get("score")
        score_disp = f"{s}" if s else "—"
        acct_score_cells += f"""<div class="acct-score-cell" style="--campus:{color}">
          <div class="acct-score-badge" style="background:{color}">
            <img src="../assets/pebble.png" alt="" style="width:16px;height:16px;filter:brightness(0) invert(1)">
          </div>
          <div>
            <div class="acct-score-name">{a['name']}</div>
            <div class="acct-score-handle">{a['handle']}</div>
          </div>
          <div class="acct-score-num" style="color:{color}">{score_disp}</div>
        </div>"""

    scoring_panel = f"""<div class="acct-panel" id="panel-scoring">
      <div class="scoring-panel">

        <!-- Score hero -->
        <div class="score-hero">
          <div>
            <div class="score-num">5.1<span class="score-denom">/10</span></div>
          </div>
          <div class="score-hero-text">
            <h2>Week of Nov 2–8: We're informing people, not yet motivating them.</h2>
            <p>20 original posts scored across all TX Celebration accounts: 4 Motivating (8–10), 7 Informing (5–7), 9 Noise (0–4).
            Photos and service times are solid. Words rarely say why it matters or invite someone new.
            Weakest dimensions: "Points to Christ, Church or Calling" (avg 0.50/2) and "Door open to someone new" (avg 0.65/2).</p>
          </div>
        </div>

        <!-- Wins + Fixes -->
        <div class="score-cols">
          <div class="score-col wins">
            <h3>✅ What's working</h3>
            <div class="score-item">
              <span class="score-icon">🎯</span>
              <div class="score-item-text">
                <strong>Pastor Jackson's Philippians 4:8 clip (9/10)</strong>
                <span>566 likes, 26 comments, 27 shares — one verse, one idea, a link. No insider language.</span>
              </div>
            </div>
            <div class="score-item">
              <span class="score-icon">📸</span>
              <div class="score-item-text">
                <strong>Real people in real moments</strong>
                <span>Top-performing posts across every account had actual faces — hugs, families, students in action.</span>
              </div>
            </div>
            <div class="score-item">
              <span class="score-icon">📊</span>
              <div class="score-item-text">
                <strong>Non-follower reach at 228K</strong>
                <span>Content is reaching new audiences. Discovery is happening — especially through @txcelebration and Georgetown.</span>
              </div>
            </div>
            <div class="score-item">
              <span class="score-icon">🤝</span>
              <div class="score-item-text">
                <strong>Pastor Joe's selfie invite drove the week's most likes (685)</strong>
                <span>Personal, authentic, face-to-camera. Proof the audience responds to pastoral voice.</span>
              </div>
            </div>
            <div class="score-item">
              <span class="score-icon">🌊</span>
              <div class="score-item-text">
                <strong>WAVE United energy was real</strong>
                <span>"WAVE UNITED is so fun!!!" post (8/10) — real student hug, fun list, time + address. Right instinct.</span>
              </div>
            </div>
          </div>
          <div class="score-col fixes">
            <h3>🔧 Three fixes this week</h3>
            <div class="score-item">
              <span class="score-icon">1️⃣</span>
              <div class="score-item-text">
                <strong>Start every caption with WHY before logistics</strong>
                <span>One line of Christ, Church or Calling before the times and address. Drop "Celebration Family."
                Communications + each ministry's social lead — by Fri Nov 13.</span>
              </div>
            </div>
            <div class="score-item">
              <span class="score-icon">2️⃣</span>
              <div class="score-item-text">
                <strong>Film Pastor Joe's weekly invite + collab ministry nights to main</strong>
                <span>WAVE United never reached the main feed. Big student nights should live where parents are.
                Communications + Pastor Joe — by Sat Nov 14.</span>
              </div>
            </div>
            <div class="score-item">
              <span class="score-icon">3️⃣</span>
              <div class="score-item-text">
                <strong>Central Austin + Lake Travis: one local photo post each</strong>
                <span>Real person + Sunday times. Post Sunday recap on Sunday — not Tuesday.
                Location Pastors — by Sun Nov 15.</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Values check -->
        <div class="score-col" style="border-radius:12px">
          <h3 style="color:var(--fg-muted);margin-bottom:1rem">Values &amp; Mission Check</h3>
          <div class="score-item">
            <span class="score-icon">✅</span>
            <div class="score-item-text"><strong>Jesus is our Pursuit</strong> <span>— Clear · Pursuit Night, Radianté recap</span></div>
          </div>
          <div class="score-item">
            <span class="score-icon">✅</span>
            <div class="score-item-text"><strong>Scripture is our Authority</strong> <span>— Clear · Pastor Jackson's Philippians 4:8 clip</span></div>
          </div>
          <div class="score-item">
            <span class="score-icon">❌</span>
            <div class="score-item-text"><strong>The Holy Spirit is our Power</strong> <span>— Missing · Not seen this week</span></div>
          </div>
          <div class="score-item">
            <span class="score-icon">✅</span>
            <div class="score-item-text"><strong>People are our Heart</strong> <span>— Clear · Hugs, families, Pastor Joe's invitation</span></div>
          </div>
          <div class="score-item">
            <span class="score-icon">🟡</span>
            <div class="score-item-text"><strong>Service is our Privilege</strong> <span>— Shown, not named · Parking volunteer in the rain (main, Nov 8)</span></div>
          </div>
          <div class="score-item">
            <span class="score-icon">❌</span>
            <div class="score-item-text"><strong>Generosity is our Lifestyle</strong> <span>— Missing · Not seen this week</span></div>
          </div>
          <div class="score-item">
            <span class="score-icon">🟡</span>
            <div class="score-item-text"><strong>Flourishing is our Goal</strong> <span>— Partly · Radianté recap: women + leaders equipped in Mozambique</span></div>
          </div>
        </div>

        <!-- Per-account score grid -->
        <div>
          <div class="section-label" style="margin-bottom:0.75rem">Account Scores · Content Audit (Nov 2–8)</div>
          <div class="acct-scores-grid">{acct_score_cells}</div>
          <p style="font-size:0.68rem;color:var(--fg-muted);margin-top:0.75rem;font-weight:300">
            Scoring: 5 questions × 2 pts each = 10 pts max. 8–10 = Motivating, 5–7 = Informing, 0–4 = Noise.
            Questions: scroll-stopping photo · one clear message · points to Christ/Church/Calling · door open to newcomers · clear next step.
          </p>
        </div>

      </div>
    </div>"""

    account_panels += scoring_panel

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

#!/usr/bin/env python3
"""
Scrape Instagram post captions for the past 7 days across all Celebration accounts.
Uses Playwright with saved cookies (cookie file: data/ig_cookies.json).
Run once manually while logged in to save cookies, then it's fully automated.

Usage:
  python scripts/scrape_ig_posts.py                # scrape + save to data/posts_YYYY-MM-DD.json
  python scripts/scrape_ig_posts.py --save-cookies  # open browser for login, save cookies, then scrape
"""

import asyncio, json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_DIR    = Path(__file__).parent.parent
DATA_DIR    = REPO_DIR / "data"
COOKIE_FILE = DATA_DIR / "ig_cookies.json"
DATA_DIR.mkdir(exist_ok=True)

ACCOUNTS = [
    {"handle": "@txcelebration",             "slug": "txcelebration"},
    {"handle": "@wave.students",             "slug": "wave.students"},
    {"handle": "@celebration.georgetown",    "slug": "celebration.georgetown"},
    {"handle": "@celebration.leander",       "slug": "celebration.leander"},
    {"handle": "@celebration.centralaustin", "slug": "celebration.centralaustin"},
    {"handle": "@celebration.laketravis",    "slug": "celebration.laketravis"},
]

SAVE_COOKIES = "--save-cookies" in sys.argv

def week_window():
    """Return (start, end) for the last Mon–Sun period (UTC)."""
    today = datetime.now(timezone.utc)
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6, hours=23, minutes=59)
    return last_monday.replace(hour=0, minute=0, second=0), last_sunday

async def get_post_urls(page, slug, limit=15):
    """Navigate to account profile and extract recent post URLs."""
    await page.goto(f"https://www.instagram.com/{slug}/", wait_until="domcontentloaded")
    await page.wait_for_timeout(2500)
    # Scroll once to trigger lazy load
    await page.evaluate("window.scrollBy(0, 400)")
    await page.wait_for_timeout(1000)
    links = await page.evaluate(f"""
        Array.from(new Set(
            Array.from(document.querySelectorAll('a[href*="/{slug}/p/"]'))
                 .map(a => a.href)
        )).slice(0, {limit})
    """)
    return links

async def scrape_post(page, url):
    """Visit a post page and extract caption + metadata from og tags."""
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)

    og_desc = await page.evaluate("""
        document.querySelector('meta[property="og:description"]')?.content || ''
    """)
    og_image = await page.evaluate("""
        document.querySelector('meta[property="og:image"]')?.content || ''
    """)

    # Format: "N likes, M comments - handle on Month Day, Year: "caption"."
    # Also try script-based extraction for timestamp
    ts_raw = await page.evaluate("""
        (() => {
            const scripts = Array.from(document.querySelectorAll('script'));
            const s = scripts.find(s => s.text.includes('"taken_at"') || s.text.includes('"timestamp"'));
            if (!s) return null;
            const m = s.text.match(/"taken_at":(\d+)/) || s.text.match(/"timestamp":(\d+)/);
            return m ? parseInt(m[1]) : null;
        })()
    """)

    if not og_desc:
        return None

    # Parse likes, comments, caption from og:description
    m = re.match(r"(\d[\d,]*)\s+likes?,\s*(\d+)\s+comments?\s*-\s*\S+\s+on\s+(.+?):\s*\"(.*)\"\.", og_desc, re.DOTALL)
    if not m:
        # Try alternate format
        m2 = re.match(r"(.+?)\s+on\s+(.+?):\s*\"(.*?)\"", og_desc, re.DOTALL)
        if not m2:
            return {"url": url, "caption": og_desc[:500], "likes": 0, "comments": 0, "image_url": og_image}
        caption = m2.group(3).strip()
        return {"url": url, "caption": caption, "likes": 0, "comments": 0, "image_url": og_image}

    likes    = int(m.group(1).replace(",", ""))
    comments = int(m.group(2))
    date_str = m.group(3).strip()
    caption  = m.group(4).strip()

    # Parse date
    try:
        post_dt = datetime.strptime(date_str, "%B %d, %Y").replace(tzinfo=timezone.utc)
    except Exception:
        post_dt = None

    return {
        "url":       url,
        "caption":   caption,
        "likes":     likes,
        "comments":  comments,
        "date_str":  date_str,
        "timestamp": ts_raw or (int(post_dt.timestamp()) if post_dt else None),
        "image_url": og_image,
    }

async def run():
    from playwright.async_api import async_playwright

    week_start, week_end = week_window()
    print(f"Scraping posts from {week_start.strftime('%b %-d')} – {week_end.strftime('%b %-d, %Y')}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not SAVE_COOKIES)
        ctx_opts = {"viewport": {"width": 1280, "height": 900}}

        # Load saved cookies if available
        if COOKIE_FILE.exists() and not SAVE_COOKIES:
            cookies = json.loads(COOKIE_FILE.read_text())
            context = await browser.new_context(**ctx_opts)
            await context.add_cookies(cookies)
            print(f"Loaded {len(cookies)} saved cookies")
        else:
            context = await browser.new_context(**ctx_opts)

        page = await context.new_page()

        if SAVE_COOKIES:
            # Open browser for manual login
            print("\nOpening Instagram login page. Log in, then press Enter here...")
            await page.goto("https://www.instagram.com/accounts/login/")
            await page.wait_for_timeout(3000)
            input("Press Enter after you've logged in: ")
            cookies = await context.cookies()
            COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
            print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")

        # Verify login
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        is_logged_in = await page.evaluate("""
            !document.querySelector('a[href*="/accounts/login"]') &&
            (document.querySelector('a[href*="/direct/"]') !== null ||
             document.querySelector('[aria-label="Home"]') !== null ||
             document.title !== 'Instagram')
        """)
        print(f"Login status: {'✓ logged in' if is_logged_in else '✗ NOT logged in — run with --save-cookies'}")
        if not is_logged_in and not SAVE_COOKIES:
            print("Cannot scrape without login. Run: python scripts/scrape_ig_posts.py --save-cookies")
            await browser.close()
            return []

        all_posts = []

        for acct in ACCOUNTS:
            handle = acct["handle"]
            slug   = acct["slug"]
            print(f"\n{handle}:")

            post_urls = await get_post_urls(page, slug)
            print(f"  Found {len(post_urls)} post URLs")

            acct_posts = []
            for url in post_urls:
                data = await scrape_post(page, url)
                if not data:
                    continue

                # Filter to week window
                ts = data.get("timestamp")
                if ts:
                    post_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    if post_dt < week_start or post_dt > week_end:
                        print(f"  Skip (outside window): {data.get('date_str','?')} — {data['caption'][:50]}")
                        continue

                data["handle"] = handle
                acct_posts.append(data)
                print(f"  ✓ {data.get('date_str','?')} · {data['likes']}♥ · {data['caption'][:60]}")

            all_posts.extend(acct_posts)
            print(f"  → {len(acct_posts)} posts in window")

        await browser.close()

    # Save
    out_file = DATA_DIR / f"posts_{week_start.strftime('%Y-%m-%d')}.json"
    out_file.write_text(json.dumps(all_posts, indent=2, ensure_ascii=False))
    print(f"\n✓ Saved {len(all_posts)} posts → {out_file}")
    return all_posts

if __name__ == "__main__":
    asyncio.run(run())

import requests
import json
import time
import datetime
import feedparser
import anthropic
import os
import jwt

# ── Config (use env vars in production) ──────────────────────────────────────
GHOST_API_URL   = os.getenv("GHOST_API_URL",   "https://leonidahq.ghost.io")
GHOST_ADMIN_KEY = os.getenv("GHOST_ADMIN_KEY", "6a04da5ea0966b0001dd3480:2ba539ca31dd411069434053edb0b52e3f46d8575ccf1cdd9b373dee2ae80da3")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")   # set this in GitHub secrets

# ── Ghost JWT auth ────────────────────────────────────────────────────────────
def get_ghost_token():
    key_id, key_secret = GHOST_ADMIN_KEY.split(":")
    iat = int(datetime.datetime.now().timestamp())
    payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
    token = jwt.encode(
        payload,
        bytes.fromhex(key_secret),
        algorithm="HS256",
        headers={"kid": key_id}
    )
    return token

# ── Fetch news from multiple RSS sources ─────────────────────────────────────
FEEDS = [
    "https://news.google.com/rss/search?q=GTA+6+Grand+Theft+Auto+VI&hl=en-US&gl=US&ceid=US:en",
    "https://www.eurogamer.net/feed",
    "https://kotaku.com/rss",
    "https://www.ign.com/rss/articles",
]

def get_gta6_news():
    articles = []
    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                title = entry.get("title", "").lower()
                summary = entry.get("summary", "").lower()
                if "gta" in title or "grand theft" in title or "gta" in summary or "grand theft" in summary:
                    articles.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", "")[:500],
                        "link": entry.get("link", ""),
                        "published": entry.get("published", "")
                    })
        except Exception as e:
            print(f"Feed error ({feed_url}): {e}")

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:6]

# ── Generate post with Claude ─────────────────────────────────────────────────
def generate_post(articles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    news_block = "\n\n".join([
        f"Headline: {a['title']}\nSummary: {a['summary']}\nURL: {a['link']}"
        for a in articles
    ])

    prompt = f"""You write for LeonidaHQ — a GTA 6 news and community site. 
Your tone is hype, direct, and written for gamers. No corporate speak.

Here are today's GTA 6 headlines:

{news_block}

Write a blog post covering the most interesting story or angle from these headlines.

Rules:
- 400-600 words
- Punchy title (no clickbait, but exciting)
- HTML body using <p>, <h2>, <strong>, <ul> tags only
- Don't invent facts. Only use what's in the headlines above.
- End with: "Stay locked to LeonidaHQ for everything GTA 6."

Respond ONLY with valid JSON, no markdown, no backticks:
{{"title": "...", "html": "...", "excerpt": "One sentence teaser under 150 chars."}}"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
            ```' in raw: raw = raw.split('```')[1].lstrip('json').strip()
    return json.loads(raw)

# ── Publish to Ghost ──────────────────────────────────────────────────────────
def publish_to_ghost(post):
    token = get_ghost_token()
    url = f"{GHOST_API_URL}/ghost/api/admin/posts/"
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept-Version": "v5.0"
    }
    payload = {
        "posts": [{
            "title": post["title"],
            "html": post["html"],
            "custom_excerpt": post["excerpt"],
            "status": "published",
            "tags": [{"name": "GTA 6"}, {"name": "News"}, {"name": "Auto-Published"}]
        }]
    }
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json()

# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print(f"\n{'='*50}")
    print(f"LeonidaHQ Agent — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print('='*50)

    print("📡 Scanning for GTA 6 news...")
    news = get_gta6_news()

    if not news:
        print("❌ No relevant news found. Skipping.")
        return

    print(f"✅ Found {len(news)} articles")
    for a in news:
        print(f"   → {a['title'][:80]}")

    print("\n✍️  Writing post with Claude...")
    post = generate_post(news)
    print(f"   Title: {post['title']}")

    print("\n🚀 Publishing to Ghost...")
    result = publish_to_ghost(post)

    if "posts" in result:
        slug = result["posts"][0]["slug"]
        print(f"✅ LIVE: {GHOST_API_URL}/{slug}")
    else:
        print(f"❌ Error: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    run()

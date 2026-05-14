import requests
import json
import datetime
import feedparser
import anthropic
import os
import jwt
import tweepy

GHOST_API_URL   = os.getenv("GHOST_API_URL",   "https://leonidahq.ghost.io")
GHOST_ADMIN_KEY = os.getenv("GHOST_ADMIN_KEY", "")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")

TWITTER_API_KEY             = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET          = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN        = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

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

FEEDS = [
    "https://news.google.com/rss/search?q=GTA+6&hl=en-US&gl=US&ceid=US:en",
    "https://www.eurogamer.net/feed",
    "https://kotaku.com/rss",
    "https://www.ign.com/rss/articles",
    "https://www.pcgamer.com/rss",
]

def get_gta6_news():
    articles = []
    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                title_lower = title.lower()
                summary_lower = summary.lower()
                if "gta" in title_lower or "grand theft" in title_lower or "gta" in summary_lower or "grand theft" in summary_lower:
                    articles.append({
                        "title": title,
                        "summary": summary[:500],
                        "link": entry.get("link", ""),
                    })
        except Exception as e:
            print(f"Feed error: {e}")

    seen = set()
    unique = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:6]

def generate_post(articles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    news_block = "\n\n".join([
        f"Headline: {a['title']}\nSummary: {a['summary']}\nURL: {a['link']}"
        for a in articles
    ])

    prompt = f"""You write for LeonidaHQ, a GTA 6 news site. Tone is hype and direct, written for gamers.

Here are today's GTA 6 headlines:

{news_block}

Write a blog post covering the most interesting story from these headlines.

Rules:
- 400-600 words
- Punchy title
- HTML body using only <p>, <h2>, <strong>, <ul> tags
- Do not invent facts
- End with: Stay locked to LeonidaHQ for everything GTA 6.

Also write a tweet (max 250 chars) teasing the article. Include the article title and end with leonidahq.gg

Respond ONLY with a raw JSON object. No markdown. No backticks. Just raw JSON:
{{"title": "article title", "html": "html body", "excerpt": "one sentence teaser under 150 chars", "tweet": "tweet text under 250 chars"}}"""

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                raw = part
                break

    return json.loads(raw)

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
            "tags": [{"name": "GTA 6"}, {"name": "News"}]
        }]
    }
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json()

def post_to_twitter(tweet_text):
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        response = client.create_tweet(text=tweet_text)
        return response.data["id"]
    except Exception as e:
        print(f"Twitter error: {e}")
        return None

def run():
    print("LeonidaHQ Agent - " + datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))

    print("Scanning for GTA 6 news...")
    news = get_gta6_news()

    if not news:
        print("No relevant news found. Skipping.")
        return

    print(f"Found {len(news)} articles")
    for a in news:
        print("  -> " + a['title'][:80])

    print("Writing post with Claude...")
    post = generate_post(news)
    print("Title: " + post['title'])

    print("Publishing to Ghost...")
    result = publish_to_ghost(post)

    if "posts" in result:
        slug = result["posts"][0]["slug"]
        post_url = f"{GHOST_API_URL}/{slug}"
        print("LIVE: " + post_url)

        print("Posting to Twitter...")
        tweet = post.get("tweet", f"New post: {post['title']} — leonidahq.gg")
        tweet_id = post_to_twitter(tweet)
        if tweet_id:
            print(f"Tweeted: https://x.com/LeonidaHQgg/status/{tweet_id}")
        else:
            print("Tweet failed — post still published to Ghost")
    else:
        print("Ghost error: " + json.dumps(result, indent=2))

if __name__ == "__main__":
    run()

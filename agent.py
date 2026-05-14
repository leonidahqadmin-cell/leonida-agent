import requests
import json
import datetime
import feedparser
import anthropic
import os
import jwt
import tweepy
import random

GHOST_API_URL   = os.getenv("GHOST_API_URL",   "https://leonidahq.ghost.io")
GHOST_ADMIN_KEY = os.getenv("GHOST_ADMIN_KEY", "")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")

TWITTER_API_KEY             = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET          = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN        = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

UNSPLASH_ACCESS_KEY         = os.getenv("UNSPLASH_ACCESS_KEY", "")

PUBLIC_SITE_URL = "https://leonidahq.gg"

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

def get_recent_ghost_titles():
    try:
        token = get_ghost_token()
        url = GHOST_API_URL + "/ghost/api/admin/posts/?limit=30&order=created_at%20desc&fields=title"
        headers = {
            "Authorization": "Ghost " + token,
            "Accept-Version": "v5.0"
        }
        resp = requests.get(url, headers=headers)
        data = resp.json()
        return [p["title"] for p in data.get("posts", [])]
    except Exception as e:
        print("Failed to fetch recent posts: " + str(e))
        return []

def get_unsplash_image(query):
    """Fetch a contextually relevant landscape image from Unsplash."""
    if not UNSPLASH_ACCESS_KEY:
        print("No Unsplash key - skipping image")
        return None
    try:
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "per_page": 10,
            "orientation": "landscape",
            "content_filter": "high"
        }
        headers = {"Authorization": "Client-ID " + UNSPLASH_ACCESS_KEY}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        if data.get("results"):
            chosen = random.choice(data["results"][:5])
            print("Unsplash image: " + chosen["urls"]["regular"][:80])
            return chosen["urls"]["regular"]
    except Exception as e:
        print("Unsplash error: " + str(e))
    return None

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
            print("Feed error: " + str(e))

    seen = set()
    unique = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    return unique[:8]

def generate_post(articles, existing_titles):
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    news_block = "\n\n".join([
        "Headline: " + a["title"] + "\nSummary: " + a["summary"] + "\nURL: " + a["link"]
        for a in articles
    ])

    existing_block = "\n".join(["- " + t for t in existing_titles[:30]]) if existing_titles else "(none yet)"

    prompt = """You write for LeonidaHQ, a GTA 6 news site. Tone is hype and direct, written for gamers.

ALREADY COVERED — DO NOT WRITE ANOTHER POST ABOUT ANY OF THESE TOPICS:
""" + existing_block + """

NEW HEADLINES AVAILABLE TODAY:

""" + news_block + """

Pick ONE headline covering a topic NOT already in the "already covered" list. If a story is about the same topic as one already covered (even with different wording), skip it.

If EVERY available headline is already covered, respond with exactly: {"skip": true, "reason": "all topics already covered"}

Otherwise, write a blog post on the chosen story.

Rules:
- 400-600 words
- Punchy title (different angle from already-covered titles)
- HTML body using only <p>, <h2>, <strong>, <ul> tags
- Do not invent facts
- End with: Stay locked to LeonidaHQ for everything GTA 6.

Also include:
- A tweet (max 230 chars, leave room for URL) teasing the article
- image_query: 2-3 keywords describing the IDEAL image for this article. Be specific to the story. Examples: "miami neon nightlife", "rockstar games office", "ps5 console", "angry gamer". Avoid generic terms like "GTA 6" since they wont return relevant photos.

Respond ONLY with raw JSON, no markdown, no backticks:
{"title": "...", "html": "...", "excerpt": "...", "tweet": "...", "image_query": "..."}"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
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

def publish_to_ghost(post, image_url):
    token = get_ghost_token()
    url = GHOST_API_URL + "/ghost/api/admin/posts/"
    headers = {
        "Authorization": "Ghost " + token,
        "Content-Type": "application/json",
        "Accept-Version": "v5.0"
    }
    post_payload = {
        "title": post["title"],
        "html": post["html"],
        "custom_excerpt": post["excerpt"],
        "status": "published",
        "tags": [{"name": "GTA 6"}, {"name": "News"}]
    }
    if image_url:
        post_payload["feature_image"] = image_url
        post_payload["feature_image_alt"] = post["title"][:125]

    payload = {"posts": [post_payload]}
    resp = requests.post(url, headers=headers, json=payload)
    return resp.json()

def post_to_twitter(tweet_text, public_url):
    full_tweet = tweet_text + "\n\n" + public_url
    if len(full_tweet) > 280:
        # Trim tweet text to fit URL
        max_text = 280 - len(public_url) - 4
        full_tweet = tweet_text[:max_text].rstrip() + "...\n\n" + public_url

    print("Tweet: " + full_tweet)
    print("Length: " + str(len(full_tweet)))
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        response = client.create_tweet(text=full_tweet)
        return response.data["id"]
    except Exception as e:
        print("Twitter error: " + str(e))
        return None

def run():
    print("LeonidaHQ Agent - " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))

    print("Checking what's already been covered...")
    existing = get_recent_ghost_titles()
    print("Found " + str(len(existing)) + " existing posts")

    print("Scanning for GTA 6 news...")
    news = get_gta6_news()

    if not news:
        print("No relevant news found. Skipping.")
        return

    print("Found " + str(len(news)) + " articles")
    for a in news:
        print("  -> " + a["title"][:80])

    print("Writing post with Claude (avoiding duplicates)...")
    post = generate_post(news, existing)

    if post.get("skip"):
        print("Skipped: " + post.get("reason", "no new topics"))
        return

    print("Title: " + post["title"])
    print("Image query: " + post.get("image_query", "(none)"))

    print("Fetching matching image from Unsplash...")
    image_url = get_unsplash_image(post.get("image_query", "miami neon"))

    print("Publishing to Ghost...")
    result = publish_to_ghost(post, image_url)

    if "posts" in result:
        slug = result["posts"][0]["slug"]
        public_post_url = PUBLIC_SITE_URL + "/" + slug + "/"
        print("LIVE: " + public_post_url)

        print("Posting to Twitter...")
        tweet_id = post_to_twitter(post.get("tweet", post["title"]), public_post_url)
        if tweet_id:
            print("Tweeted: https://x.com/LeonidaHQgg/status/" + str(tweet_id))
        else:
            print("Tweet failed - post still published to Ghost")
    else:
        print("Ghost error: " + json.dumps(result, indent=2))

if __name__ == "__main__":
    run()

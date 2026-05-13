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

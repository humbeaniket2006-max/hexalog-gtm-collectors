"""Read Reddit posts/comments and store matching competitive signals in Notion."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import praw

from .config import Settings, load_settings
from .notion import NotionHelper

LOG = logging.getLogger(__name__)

def matched_keywords(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    return [word for word in keywords if word.lower() in lower]

def _iso(value: Any) -> str:
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()

def _signal(item: Any, subreddit: str, kind: str, matches: list[str]) -> dict[str, Any]:
    is_post = kind == "post"
    body = getattr(item, "selftext", "") if is_post else getattr(item, "body", "")
    title = getattr(item, "title", "") if is_post else f"Comment in r/{subreddit}"
    url = "https://www.reddit.com" + getattr(item, "permalink", "")
    return {"Title": title[:2000], "Platform": "Reddit", "Source": subreddit, "External ID": item.id,
            "Type": kind, "URL": url, "Author/Channel": str(getattr(item, "author", "[deleted]")),
            "Published At": _iso(item.created_utc), "Matched Keywords": ", ".join(matches),
            "Score/Views": getattr(item, "score", 0), "Comments Count": getattr(item, "num_comments", 0) if is_post else None,
            "Snippet": (body or title)[:500], "Collected At": datetime.now(timezone.utc).isoformat()}

def _rules_due(page: dict[str, Any] | None) -> bool:
    if not page: return True
    date = page.get("properties", {}).get("Fetched At", {}).get("date") or {}
    start = date.get("start")
    if not start: return True
    try: return datetime.fromisoformat(start.replace("Z", "+00:00")) < datetime.now(timezone.utc) - timedelta(days=7)
    except ValueError: return True

def _refresh_rules(notion: NotionHelper, database_id: str, subreddit: Any, name: str) -> bool:
    page = notion.find_page(database_id, "Subreddit", name)
    if not _rules_due(page): return False
    summary = "\n".join(f"{r.short_name}: {r.description}" for r in subreddit.rules())[:1900]
    props = {"Title": f"r/{name} rules", "Subreddit": name, "Rules Summary": summary, "Fetched At": datetime.now(timezone.utc).isoformat()}
    if page: notion.update_page(page["id"], props)
    else: notion.create_page(database_id, props)
    return True

def collect_signals(settings: Settings | None = None, reddit: Any | None = None, notion: NotionHelper | None = None) -> None:
    settings = settings or load_settings(require_reddit=True)
    reddit = reddit or praw.Reddit(client_id=settings.reddit_client_id, client_secret=settings.reddit_client_secret, user_agent=settings.reddit_user_agent, read_only=True)
    notion = notion or NotionHelper(settings.notion_api_key)
    signals_id, rules_id = notion.find_database_id("Competitor Signals"), notion.find_database_id("Subreddit Rules")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=26)
    for name in settings.reddit_subreddits:
        posts_added = comments_added = 0
        try:
            sub = reddit.subreddit(name)
            refreshed = _refresh_rules(notion, rules_id, sub, name)
            for post in sub.new(limit=100):
                if datetime.fromtimestamp(post.created_utc, timezone.utc) < cutoff: continue
                matches = matched_keywords(f"{post.title} {post.selftext}", settings.reddit_keywords)
                if matches and not notion.page_exists(signals_id, post.id):
                    notion.create_page(signals_id, _signal(post, name, "post", matches)); posts_added += 1
            # Recent existing Reddit submissions are intentionally re-fetched for new top-level comments.
            result = notion.query(signals_id, {"property": "Platform", "select": {"equals": "Reddit"}})
            for page in result.get("results", []):
                ext = page.get("properties", {}).get("External ID", {}).get("rich_text", [])
                if not ext: continue
                post = reddit.submission(id=ext[0]["plain_text"])
                post.comments.replace_more(limit=0)
                for comment in post.comments:
                    if datetime.fromtimestamp(comment.created_utc, timezone.utc) < datetime.now(timezone.utc) - timedelta(days=3): continue
                    matches = matched_keywords(comment.body, settings.reddit_keywords)
                    if matches and not notion.page_exists(signals_id, comment.id):
                        notion.create_page(signals_id, _signal(comment, name, "comment", matches)); comments_added += 1
            LOG.info("r/%s: posts=%s comments=%s rules_refreshed=%s", name, posts_added, comments_added, refreshed)
        except Exception:
            LOG.exception("Failed collecting r/%s; continuing", name)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collect_signals()

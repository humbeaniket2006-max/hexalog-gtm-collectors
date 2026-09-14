"""Read Reddit posts/comments and store matching competitive signals in Notion.

Runs two passes per collect_signals() call:
  Pass A — a pain-point sweep of the fixed REDDIT_SUBREDDITS list (new posts plus
    top-level comments on posts already logged from those subreddits).
  Pass B — a site-wide search for each REDDIT_COMPETITOR_KEYWORDS name across all of
    Reddit, since the most useful competitor-sentiment signal often comes from a
    subreddit nobody pre-selected. Source is whichever subreddit the result actually
    came from.
Both passes dedupe against the same "Competitor Signals" database by Reddit post/comment
ID, so a post that matches both passes is only ever logged once.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import praw

from .config import Settings, load_settings
from .notion import NotionHelper

LOG = logging.getLogger(__name__)

# Heuristic hints that a competitor-name mention is about cross-border/brand sentiment
# rather than unrelated noise (e.g. a purely domestic delivery-tracking complaint).
COMPETITOR_RELEVANCE_HINTS = [
    "international", "export", "import", "cross border", "review",
    "alternative", "vs", "experience", "feedback",
]


def matched_keywords(text: str, keywords: list[str]) -> list[str]:
    lower = text.lower()
    return [word for word in keywords if word.lower() in lower]


def is_relevant_competitor_mention(text: str) -> bool:
    lower = text.lower()
    return any(hint in lower for hint in COMPETITOR_RELEVANCE_HINTS)


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


def _collect_pain_point_sweep(settings: Settings, reddit: Any, notion: NotionHelper, signals_id: str, rules_id: str) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=26)
    comment_cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    for name in settings.reddit_subreddits:
        posts_added = comments_added = 0
        try:
            sub = reddit.subreddit(name)
            refreshed = _refresh_rules(notion, rules_id, sub, name)
            for post in sub.new(limit=100):
                if datetime.fromtimestamp(post.created_utc, timezone.utc) < cutoff: continue
                matches = matched_keywords(f"{post.title} {post.selftext}", settings.reddit_pain_point_keywords)
                if matches and not notion.page_exists(signals_id, post.id):
                    notion.create_page(signals_id, _signal(post, name, "post", matches)); posts_added += 1
            # Recent existing Reddit submissions from this subreddit are re-fetched for new top-level comments.
            existing = notion.query(signals_id, {"and": [
                {"property": "Platform", "select": {"equals": "Reddit"}},
                {"property": "Source", "rich_text": {"equals": name}},
            ]})
            for page in existing.get("results", []):
                ext = page.get("properties", {}).get("External ID", {}).get("rich_text", [])
                if not ext: continue
                post = reddit.submission(id=ext[0]["plain_text"])
                post.comments.replace_more(limit=0)
                for comment in post.comments:
                    if datetime.fromtimestamp(comment.created_utc, timezone.utc) < comment_cutoff: continue
                    matches = matched_keywords(comment.body, settings.reddit_pain_point_keywords)
                    if matches and not notion.page_exists(signals_id, comment.id):
                        notion.create_page(signals_id, _signal(comment, name, "comment", matches)); comments_added += 1
            LOG.info("Pass A r/%s: posts=%s comments=%s rules_refreshed=%s", name, posts_added, comments_added, refreshed)
            summary[name] = {"posts": posts_added, "comments": comments_added}
        except Exception:
            LOG.exception("Pass A failed for r/%s; continuing", name)
            summary[name] = {"posts": posts_added, "comments": comments_added, "error": True}
    return summary


def _collect_competitor_search(settings: Settings, reddit: Any, notion: NotionHelper, signals_id: str) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for keyword in settings.reddit_competitor_keywords:
        added = 0
        subreddits_hit: dict[str, int] = {}
        try:
            results = reddit.subreddit("all").search(keyword, sort="new", time_filter="month", limit=25)
            for post in results:
                text = f"{getattr(post, 'title', '')} {getattr(post, 'selftext', '')}"
                if not is_relevant_competitor_mention(text): continue
                source = str(getattr(post.subreddit, "display_name", post.subreddit))
                if notion.page_exists(signals_id, post.id): continue
                notion.create_page(signals_id, _signal(post, source, "post", [keyword]))
                added += 1
                subreddits_hit[source] = subreddits_hit.get(source, 0) + 1
            LOG.info("Pass B %r: %s new posts across subreddits %s", keyword, added, subreddits_hit)
            summary[keyword] = {"added": added, "subreddits": subreddits_hit}
        except Exception:
            LOG.exception("Pass B failed for competitor keyword %r; continuing", keyword)
            summary[keyword] = {"added": added, "subreddits": subreddits_hit, "error": True}
    return summary


def collect_signals(settings: Settings | None = None, reddit: Any | None = None, notion: NotionHelper | None = None) -> None:
    settings = settings or load_settings(require_reddit=True)
    reddit = reddit or praw.Reddit(client_id=settings.reddit_client_id, client_secret=settings.reddit_client_secret, user_agent=settings.reddit_user_agent, read_only=True)
    notion = notion or NotionHelper(settings.notion_api_key)
    signals_id, rules_id = notion.find_database_id("Competitor Signals"), notion.find_database_id("Subreddit Rules")

    pass_a_summary = _collect_pain_point_sweep(settings, reddit, notion, signals_id, rules_id)
    pass_b_summary = _collect_competitor_search(settings, reddit, notion, signals_id)

    LOG.info("Summary — Pass A (pain-point sweep) new items by subreddit: %s", pass_a_summary)
    LOG.info("Summary — Pass B (competitor search) new posts by keyword: %s", {k: v["added"] for k, v in pass_b_summary.items()})
    LOG.info("Summary — Pass B subreddits actually matched, by keyword: %s", {k: v["subreddits"] for k, v in pass_b_summary.items()})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collect_signals()

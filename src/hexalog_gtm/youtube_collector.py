"""Quota-conscious YouTube competitor-video collector."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any
from googleapiclient.discovery import build
from .config import Settings, load_settings
from .notion import NotionHelper
LOG = logging.getLogger(__name__)

def collect_signals(settings: Settings | None = None, youtube: Any | None = None, notion: NotionHelper | None = None) -> None:
    settings = settings or load_settings(require_youtube=True)
    youtube = youtube or build("youtube", "v3", developerKey=settings.youtube_api_key)
    notion = notion or NotionHelper(settings.notion_api_key)
    database_id, units = notion.find_database_id("Competitor Signals"), 0
    for label, channel_id in settings.youtube_channels.items():
        try:
            channel = youtube.channels().list(part="contentDetails", id=channel_id).execute(); units += 1
            entries = channel.get("items", [])
            if not entries: LOG.warning("No channel found for %s", label); continue
            playlist = entries[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            items = youtube.playlistItems().list(part="contentDetails", playlistId=playlist, maxResults=50).execute().get("items", []); units += 1
            added = 0
            for item in items:
                video_id = item["contentDetails"]["videoId"]
                if notion.page_exists(database_id, video_id): continue
                response = youtube.videos().list(part="snippet,statistics", id=video_id).execute(); units += 1
                videos = response.get("items", [])
                if not videos: continue
                video, snippet, stats = videos[0], videos[0]["snippet"], videos[0].get("statistics", {})
                notion.create_page(database_id, {"Title": snippet["title"], "Platform": "YouTube", "Source": label, "External ID": video_id, "Type": "video", "URL": f"https://www.youtube.com/watch?v={video_id}", "Author/Channel": label, "Published At": snippet["publishedAt"], "Score/Views": int(stats.get("viewCount", 0)), "Comments Count": int(stats.get("commentCount", 0)), "Snippet": snippet.get("description", "")[:500], "Collected At": datetime.now(timezone.utc).isoformat()})
                added += 1
            LOG.info("YouTube %s: %s new videos", label, added)
        except Exception: LOG.exception("Failed collecting YouTube channel %s; continuing", label)
    LOG.info("Estimated YouTube quota units used: %s (daily cap: 10,000)", units)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); collect_signals()

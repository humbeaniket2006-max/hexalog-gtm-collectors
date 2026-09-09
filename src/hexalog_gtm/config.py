"""Environment-backed settings."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

DEFAULT_SUBREDDITS = ["freightforwarding", "IndiaBusiness", "smallbusinessindia"]
DEFAULT_KEYWORDS = ["Cogoport", "ClickPost", "Shiprocket", "WareIQ", "ShipGlobal", "customs", "landed cost", "freight forwarder", "export", "import", "cross border", "MSME"]
DEFAULT_CHANNELS = {
    "cogoport": "UCkcDvMjmhw_q3Z6c6bINTaA",
    "clickpost": "UCwzueyGjeYNWE9QWVw4QlSQ",
    "shiprocket": "UCvdTTQAnDvvwyhwVzri-Xow",
    "wareiq": "UCVKeBRblcVtkvT95R2TciAA",
    "shipglobal_in": "UCmSBjRESA2F_DBmoleUkzFw",
    "sarthak_ahuja": "UCzHDKR4zchL8NbFWMKgR0BQ",
    "paresh_solanki": "UCh9Fu-dnyAqKd4m3K0qc8bA",
    "iiiem": "UCYUXVErD8rZxEv0ZsAd4oOA",
    "export_import_india": "UC72xtAoQ3HBB8wn6so7K-GA",
}

def _json_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    return json.loads(value) if value else default

def _json_dict(name: str, default: dict[str, str]) -> dict[str, str]:
    value = os.getenv(name)
    return json.loads(value) if value else default

@dataclass(frozen=True)
class Settings:
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str
    youtube_api_key: str
    notion_api_key: str
    reddit_subreddits: list[str]
    reddit_keywords: list[str]
    youtube_channels: dict[str, str]

def load_settings(*, require_reddit: bool = False, require_youtube: bool = False) -> Settings:
    load_dotenv()
    required = ["NOTION_API_KEY"]
    if require_reddit:
        required += ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]
    if require_youtube:
        required += ["YOUTUBE_API_KEY"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required environment variable(s): " + ", ".join(missing))
    return Settings(os.getenv("REDDIT_CLIENT_ID", ""), os.getenv("REDDIT_CLIENT_SECRET", ""), os.getenv("REDDIT_USER_AGENT", ""), os.getenv("YOUTUBE_API_KEY", ""), os.getenv("NOTION_API_KEY", ""), _json_list("REDDIT_SUBREDDITS", DEFAULT_SUBREDDITS), _json_list("REDDIT_KEYWORDS", DEFAULT_KEYWORDS), _json_dict("YOUTUBE_CHANNELS", DEFAULT_CHANNELS))

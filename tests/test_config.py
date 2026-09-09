import pytest
from hexalog_gtm.config import load_settings

def test_missing_required_variable_is_named(monkeypatch):
    for key in ("NOTION_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="REDDIT_CLIENT_ID"):
        load_settings(require_reddit=True)

from types import SimpleNamespace
from hexalog_gtm.config import Settings
from hexalog_gtm.reddit_collector import collect_signals, matched_keywords

class Notion:
    def __init__(self): self.created = []
    def find_database_id(self, name): return name
    def find_page(self, *_): return None
    def query(self, *_): return {"results": []}
    def page_exists(self, _, external): return external == "duplicate"
    def create_page(self, _, props): self.created.append(props)
    def update_page(self, *_): pass

def test_keyword_matching_and_external_id_deduplication():
    assert matched_keywords("Cogoport makes export easier", ["cogoport", "import"]) == ["cogoport"]
    post = SimpleNamespace(id="duplicate", title="Cogoport", selftext="", created_utc=9999999999, permalink="/x", author="a", score=1, num_comments=0)
    rule = SimpleNamespace(short_name="r1", description="be kind")
    sub = SimpleNamespace(new=lambda limit: [post], rules=lambda: [rule])
    reddit = SimpleNamespace(subreddit=lambda _: sub)
    settings = Settings("id", "secret", "ua", "", "token", ["test"], ["cogoport"], {})
    notion = Notion(); collect_signals(settings, reddit, notion)
    assert notion.created and notion.created[0]["Title"] == "r/test rules"
    assert not any(p.get("External ID") == "duplicate" for p in notion.created)

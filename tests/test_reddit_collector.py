from datetime import datetime, timezone
from types import SimpleNamespace

from hexalog_gtm.config import Settings
from hexalog_gtm.reddit_collector import collect_signals, is_relevant_competitor_mention, matched_keywords


def _recent_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _post(id_, title, selftext="", subreddit=None, score=1, num_comments=0):
    kwargs = dict(id=id_, title=title, selftext=selftext, created_utc=_recent_ts(), permalink=f"/{id_}",
                  author="a", score=score, num_comments=num_comments)
    if subreddit is not None:
        kwargs["subreddit"] = SimpleNamespace(display_name=subreddit)
    return SimpleNamespace(**kwargs)


class FakeNotion:
    def __init__(self, existing=None):
        self.created = []
        self.existing = set(existing or [])

    def find_database_id(self, name):
        return name

    def find_page(self, *_):
        return None

    def query(self, *_):
        return {"results": []}

    def page_exists(self, _, external_id):
        return external_id in self.existing or any(p.get("External ID") == external_id for p in self.created)

    def create_page(self, _, props):
        self.created.append(props)

    def update_page(self, *_):
        pass


def _settings(subreddits=(), pain_point=(), competitor=()):
    return Settings("id", "secret", "ua", "", "token", list(subreddits), list(pain_point), list(competitor), {})


def test_keyword_matching_is_case_insensitive():
    assert matched_keywords("Cogoport makes export easier", ["cogoport", "import"]) == ["cogoport"]


def test_pass_a_matches_keywords_and_dedupes_by_external_id():
    fresh = _post("fresh", "Cogoport export costs are brutal")
    dup = _post("duplicate", "Cogoport again")
    rule = SimpleNamespace(short_name="r1", description="be kind")
    sub = SimpleNamespace(new=lambda limit: [fresh, dup], rules=lambda: [rule])
    reddit = SimpleNamespace(subreddit=lambda name: sub)
    settings = _settings(subreddits=["test"], pain_point=["cogoport"])
    notion = FakeNotion(existing={"duplicate"})

    collect_signals(settings, reddit, notion)

    logged_ids = [p["External ID"] for p in notion.created if p.get("Type") in ("post", "comment")]
    assert logged_ids == ["fresh"]


def test_pass_b_assigns_dynamic_source_and_filters_irrelevant_noise():
    relevant = _post("keep", "Shiprocket vs Cogoport for export shipments", subreddit="indianstartups")
    noise = _post("drop", "Shiprocket delivery is late again", "just a local courier complaint", subreddit="indianstartups")

    class FakeAll:
        def search(self, keyword, sort, time_filter, limit):
            return [relevant, noise]

    reddit = SimpleNamespace(subreddit=lambda name: FakeAll())
    settings = _settings(competitor=["Shiprocket"])
    notion = FakeNotion()

    collect_signals(settings, reddit, notion)

    assert [p["External ID"] for p in notion.created] == ["keep"]
    assert notion.created[0]["Source"] == "indianstartups"
    assert notion.created[0]["Matched Keywords"] == "Shiprocket"


def test_relevance_heuristic_directly():
    assert is_relevant_competitor_mention("Looking for a Shiprocket alternative for international export")
    assert not is_relevant_competitor_mention("Shiprocket courier lost my domestic package again")


def test_post_matching_both_passes_is_logged_only_once():
    pain_point_post = _post("dual", "Cogoport export nightmare, any alternative?")
    sub = SimpleNamespace(new=lambda limit: [pain_point_post], rules=lambda: [])
    search_hit = _post("dual", "Cogoport export nightmare, any alternative?", subreddit="test")

    class FakeAll:
        def search(self, keyword, sort, time_filter, limit):
            return [search_hit]

    def subreddit(name):
        return FakeAll() if name == "all" else sub

    reddit = SimpleNamespace(subreddit=subreddit)
    settings = _settings(subreddits=["test"], pain_point=["cogoport"], competitor=["Cogoport"])
    notion = FakeNotion()

    collect_signals(settings, reddit, notion)

    dual_pages = [p for p in notion.created if p.get("External ID") == "dual"]
    assert len(dual_pages) == 1
    assert dual_pages[0]["Source"] == "test"

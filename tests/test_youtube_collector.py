from types import SimpleNamespace
from hexalog_gtm.config import Settings
from hexalog_gtm.youtube_collector import collect_signals

class Request:
    def __init__(self, value): self.value = value
    def execute(self): return self.value
class Youtube:
    def channels(self): return SimpleNamespace(list=lambda **_: Request({"items":[{"contentDetails":{"relatedPlaylists":{"uploads":"pl"}}}]}))
    def playlistItems(self): return SimpleNamespace(list=lambda **_: Request({"items":[{"contentDetails":{"videoId":"new"}},{"contentDetails":{"videoId":"old"}}]}))
    def videos(self): return SimpleNamespace(list=lambda **_: Request({"items":[{"snippet":{"title":"Video","description":"desc","publishedAt":"2025-01-01T00:00:00Z"},"statistics":{"viewCount":"4","commentCount":"2"}}]}))
class Notion:
    def __init__(self): self.created=[]
    def find_database_id(self, _): return "db"
    def page_exists(self, _, key): return key == "old"
    def create_page(self, _, props): self.created.append(props)
def test_playlist_collection_and_deduplication():
    s = Settings("", "", "", "key", "token", [], [], {"channel":"id"}); n = Notion()
    collect_signals(s, Youtube(), n)
    assert [p["External ID"] for p in n.created] == ["new"]

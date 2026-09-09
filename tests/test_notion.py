from hexalog_gtm.notion import NotionHelper


def test_competitor_signal_source_is_rich_text():
    props = NotionHelper._properties({"Source": "cogoport", "Platform": "YouTube"})
    assert props["Source"] == {"rich_text": [{"type": "text", "text": {"content": "cogoport"}}]}
    assert props["Platform"] == {"select": {"name": "YouTube"}}

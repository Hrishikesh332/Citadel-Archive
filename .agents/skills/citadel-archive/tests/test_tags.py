from kb.tags import merge_tags, normalize_tag, normalize_tags


def test_normalizes_tag() -> None:
    assert normalize_tag(" Personal Notes ") == "personal-notes"


def test_normalize_tags_deduplicates() -> None:
    assert normalize_tags(["AI", "ai", "AI Systems"]) == ("ai", "ai-systems")


def test_merge_tags_keeps_order() -> None:
    assert merge_tags(["personal", "ai"], ["AI", "railway"]) == (
        "personal",
        "ai",
        "railway",
    )

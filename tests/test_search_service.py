from __future__ import annotations

from ctxsnap.services.search_service import SearchService


def test_parse_with_field_query_enabled() -> None:
    svc = SearchService()
    parsed = svc.parse('tag:work root:project todo:"write tests" plain', field_enabled=True)
    assert parsed.fields["tags"] == ["work"]
    assert parsed.fields["root"] == ["project"]
    assert parsed.fields["todos"] == ["write tests"]
    assert parsed.terms == ["plain"]


def test_match_item_with_loader_for_field_tokens() -> None:
    svc = SearchService()
    parsed = svc.parse('todo:refactor tag:work', field_enabled=True)
    item = {
        "id": "s1",
        "title": "feature work",
        "root": "C:/repo",
        "tags": ["work"],
        "search_blob": "",
    }

    def loader(_: str):
        return {
            "todos": ["refactor restore flow", "", ""],
            "note": "",
            "processes": [],
            "running_apps": [],
        }

    assert svc.matches_item(item, parsed, load_snapshot=loader) is True


def test_field_query_disabled_treats_token_as_plain_term() -> None:
    svc = SearchService()
    parsed = svc.parse("tag:work", field_enabled=False)
    item = {"id": "x", "title": "tag:work done", "root": "", "tags": [], "search_blob": ""}
    assert svc.matches_item(item, parsed, load_snapshot=None) is True

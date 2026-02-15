from __future__ import annotations

from ctxsnap.utils import parse_search_query


def test_parse_search_query_splits_filters_and_terms() -> None:
    filters, terms = parse_search_query("tag:work todo:PR pinned:true foo bar")
    assert filters["tag"] == ["work"]
    assert filters["todo"] == ["pr"]
    assert filters["pinned"] is True
    assert terms == ["foo", "bar"]


def test_parse_search_query_invalid_bool_becomes_term() -> None:
    filters, terms = parse_search_query("pinned:maybe x")
    assert "pinned" not in filters
    assert "pinned:maybe" in terms
    assert "x" in terms


def test_parse_search_query_windows_path_value_kept() -> None:
    filters, _terms = parse_search_query(r"root:C:\Repo")
    assert filters["root"] == [r"c:\repo"]


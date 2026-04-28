from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ctxsnap.utils import build_search_blob


@dataclass
class ParsedQuery:
    terms: List[str] = field(default_factory=list)
    fields: Dict[str, List[str]] = field(default_factory=dict)


class SearchService:
    """Supports free text search + optional field queries (tag:, root:, todo:...)."""

    FIELD_ALIASES = {
        "tag": "tags",
        "tags": "tags",
        "root": "root",
        "todo": "todos",
        "note": "note",
        "process": "processes",
        "app": "running_apps",
        "title": "title",
    }

    def parse(self, raw: str, *, field_enabled: bool) -> ParsedQuery:
        out = ParsedQuery()
        query = (raw or "").strip()
        if not query:
            return out
        try:
            lexer = shlex.shlex(query, posix=True)
            lexer.whitespace_split = True
            lexer.escape = ""
            tokens = list(lexer)
        except ValueError:
            tokens = query.split()
        for tok in tokens:
            if field_enabled and ":" in tok:
                key, value = tok.split(":", 1)
                key = self.FIELD_ALIASES.get(key.lower().strip(), "")
                value = value.strip().lower()
                if key and value:
                    out.fields.setdefault(key, []).append(value)
                    continue
            out.terms.append(tok.lower())
        return out

    @staticmethod
    def _contains_all(haystack: str, needles: List[str]) -> bool:
        h = haystack.lower()
        return all(n in h for n in needles)

    def matches_item(
        self,
        item: Dict[str, Any],
        parsed: ParsedQuery,
        *,
        load_snapshot: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ) -> bool:
        if not parsed.terms and not parsed.fields:
            return True

        title = str(item.get("title", "") or "")
        root = str(item.get("root", "") or "")
        tags = [str(t).lower() for t in item.get("tags", []) or []]
        base_hay = f"{title} {root} {' '.join(tags)}".lower()
        sid = str(item.get("id") or "")
        snap: Optional[Dict[str, Any]] = None

        def ensure_snapshot() -> Optional[Dict[str, Any]]:
            nonlocal snap
            if snap is None and load_snapshot and sid:
                snap = load_snapshot(sid)
            return snap

        if parsed.terms:
            cached_hay = base_hay + " " + str(item.get("search_blob", "")).lower()
            if not self._contains_all(cached_hay, parsed.terms):
                loaded = ensure_snapshot()
                runtime_hay = base_hay + " " + self.build_blob_if_missing(item, loaded).lower()
                if not self._contains_all(runtime_hay, parsed.terms):
                    return False

        if not parsed.fields:
            return True

        for field, values in parsed.fields.items():
            if field == "title":
                if not self._contains_all(title, values):
                    return False
            elif field == "root":
                if not self._contains_all(root, values):
                    return False
            elif field == "tags":
                joined = " ".join(tags)
                if not self._contains_all(joined, values):
                    return False
            elif field in {"todos", "note", "processes", "running_apps"}:
                loaded = ensure_snapshot()
                if not loaded:
                    return False
                if field == "todos":
                    hay = " ".join(str(x).lower() for x in (loaded.get("todos", []) or []))
                elif field == "note":
                    hay = str(loaded.get("note", "") or "").lower()
                elif field == "processes":
                    procs = loaded.get("processes", []) or []
                    hay = " ".join(str(p.get("name", "")).lower() + " " + str(p.get("exe", "")).lower() for p in procs if isinstance(p, dict))
                else:
                    apps = loaded.get("running_apps", []) or []
                    hay = " ".join(str(a.get("name", "")).lower() + " " + str(a.get("exe", "")).lower() for a in apps if isinstance(a, dict))
                if not self._contains_all(hay, values):
                    return False
            else:
                # Unknown field should fail closed.
                return False

        return True

    def build_blob_if_missing(self, item: Dict[str, Any], snap: Optional[Dict[str, Any]]) -> str:
        cached = str(item.get("search_blob") or "")
        if not snap:
            return cached
        runtime = build_search_blob(snap)
        return f"{cached} {runtime}".strip()

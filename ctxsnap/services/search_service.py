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
            tokens = shlex.split(query)
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

        if parsed.terms and not self._contains_all(base_hay + " " + str(item.get("search_blob", "")).lower(), parsed.terms):
            return False

        if not parsed.fields:
            return True

        sid = str(item.get("id") or "")
        snap = load_snapshot(sid) if (load_snapshot and sid) else None

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
                if not snap:
                    return False
                if field == "todos":
                    hay = " ".join(str(x).lower() for x in (snap.get("todos", []) or []))
                elif field == "note":
                    hay = str(snap.get("note", "") or "").lower()
                elif field == "processes":
                    procs = snap.get("processes", []) or []
                    hay = " ".join(str(p.get("name", "")).lower() + " " + str(p.get("exe", "")).lower() for p in procs if isinstance(p, dict))
                else:
                    apps = snap.get("running_apps", []) or []
                    hay = " ".join(str(a.get("name", "")).lower() + " " + str(a.get("exe", "")).lower() for a in apps if isinstance(a, dict))
                if not self._contains_all(hay, values):
                    return False
            else:
                # Unknown field should fail closed.
                return False

        return True

    def build_blob_if_missing(self, item: Dict[str, Any], snap: Optional[Dict[str, Any]]) -> str:
        if item.get("search_blob"):
            return str(item.get("search_blob") or "")
        if not snap:
            return ""
        return build_search_blob(snap)

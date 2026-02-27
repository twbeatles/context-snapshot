from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from PySide6 import QtGui, QtWidgets

from ctxsnap.app_storage import save_json
from ctxsnap.constants import DEFAULT_TAGS
from ctxsnap.core.logging import get_logger
from ctxsnap.i18n import tr
from ctxsnap.utils import build_search_blob, safe_parse_datetime, snapshot_mtime

LOGGER = get_logger()


class MainWindowListViewSection:
    def _build_tag_menu(self) -> None:
        menu = QtWidgets.QMenu(self)
        clear_action = QtGui.QAction("All tags", self)
        clear_action.triggered.connect(self._clear_tag_filter)
        menu.addAction(clear_action)
        menu.addSeparator()
        tags = self.settings.get("tags", DEFAULT_TAGS)
        self.selected_tags.intersection_update(tags)
        for tag in tags:
            action = QtGui.QAction(tag, self)
            action.setCheckable(True)
            action.setChecked(tag in self.selected_tags)
            action.triggered.connect(self._toggle_tag_filter)
            menu.addAction(action)
        self.tag_filter_btn.setMenu(menu)

    def _toggle_tag_filter(self) -> None:
        action = self.sender()
        if isinstance(action, QtGui.QAction):
            tag = action.text()
            if action.isChecked():
                self.selected_tags.add(tag)
            else:
                self.selected_tags.discard(tag)
        self._reset_pagination_and_refresh()

    def _clear_tag_filter(self) -> None:
        self.selected_tags.clear()
        self._build_tag_menu()
        self._reset_pagination_and_refresh()

    # ----- index helpers -----
    def _clear_search(self) -> None:
        self.search.clear()

    def _reset_pagination_and_refresh(self) -> None:
        self._current_page = 1
        self.refresh_list(reset_page=False)

    def _update_pagination_controls(self) -> None:
        self.page_prev_btn.setEnabled(self._current_page > 1)
        self.page_next_btn.setEnabled(self._current_page < self._total_pages)
        self.page_label.setText(f"Page {self._current_page} / {self._total_pages}")

    def _prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self.refresh_list(reset_page=False)

    def _next_page(self) -> None:
        if self._current_page < self._total_pages:
            self._current_page += 1
            self.refresh_list(reset_page=False)

    def refresh_list(self, *, reset_page: bool = False) -> None:
        query_raw = self.search.text().strip()
        field_query_enabled = bool(
            self.settings.get("dev_flags", {}).get("advanced_search_enabled", False)
            and self.settings.get("search", {}).get("enable_field_query", True)
        )
        parsed_query = self.search_service.parse(query_raw, field_enabled=field_query_enabled)
        if field_query_enabled and parsed_query.fields:
            LOGGER.info("search_field_query query=%s", query_raw)
        pinned_only = bool(self.pinned_only.isChecked()) if hasattr(self, "pinned_only") else False
        show_archived = bool(self.show_archived.isChecked()) if hasattr(self, "show_archived") else False

        items = list(self.index.get("snapshots", []))
        index_changed = False
        view_items: List[Dict[str, Any]] = []

        sort_mode = self.sort_combo.currentData() if hasattr(self, "sort_combo") else "newest"
        
        if sort_mode == "pinned":
            items.sort(key=lambda x: (not bool(x.get("pinned", False)), x.get("created_at", "")), reverse=False)
        elif sort_mode == "oldest":
            items.sort(key=lambda x: x.get("created_at", ""))
        elif sort_mode == "title":
            items.sort(key=lambda x: (x.get("title", "").lower(), x.get("created_at", "")))
        else: # newest or default
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        days_filter = self.days_filter.currentData() if hasattr(self, "days_filter") else "all"
        now = datetime.now()
        day_cutoff = None
        # Logic based on "1", "3", "7", "30", "all"
        if days_filter and days_filter != "all":
            try:
                days = int(days_filter)
                day_cutoff = now - timedelta(days=days)
            except Exception:
                day_cutoff = None

        for it in items:
            tags = it.get("tags", []) or []
            if self.selected_tags and not self.selected_tags.intersection(tags):
                continue
            if bool(it.get("archived", False)) and not show_archived:
                continue
            if query_raw:
                if parsed_query.terms:
                    search_blob = (it.get("search_blob") or "").lower()
                    snap_mtime = 0.0
                    if it.get("id"):
                        snap_mtime = snapshot_mtime(self.snap_path(it["id"]))
                    if it.get("search_blob_mtime", 0.0) < snap_mtime:
                        search_blob = ""
                    if not search_blob and it.get("id"):
                        snap = self.load_snapshot(it.get("id"))
                        if snap:
                            search_blob = build_search_blob(snap)
                            it["search_blob"] = search_blob
                            it["search_blob_mtime"] = snap_mtime or snapshot_mtime(self.snap_path(it["id"]))
                            index_changed = True
                if not self.search_service.matches_item(
                    it,
                    parsed_query,
                    load_snapshot=self.load_snapshot,
                ):
                    continue

            if pinned_only and not bool(it.get("pinned", False)):
                continue

            if day_cutoff:
                created_at = safe_parse_datetime(it.get("created_at", ""))
                if created_at and created_at < day_cutoff:
                    continue

            view_items.append(it)
        if index_changed:
            self.index = self.snapshot_service.touch_index(self.index)
            if not save_json(self.index_path, self.index):
                LOGGER.warning("Failed to persist search blob cache updates.")
        page_size = max(1, int(self.settings.get("list_page_size", 200)))
        total = len(view_items)
        self._total_pages = max(1, (total + page_size - 1) // page_size)
        if reset_page:
            self._current_page = 1
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages
        start = (self._current_page - 1) * page_size
        end = start + page_size
        self.list_model.set_items(view_items[start:end])
        if hasattr(self, "result_label"):
            total_all = len(self.index.get("snapshots", []))
            showing = len(view_items[start:end])
            self.result_label.setText(
                f"{tr('Storage:')} {showing} / {len(view_items)} (Total {total_all})"
            )
        self._update_pagination_controls()

    def selected_id(self) -> Optional[str]:
        idx = self.listw.currentIndex()
        if not idx.isValid():
            return None
        sid = self.list_model.id_for_index(idx)
        if not sid:
            return None
        return sid


from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional


class RestoreService:
    """Restore profile helpers and defaults resolution."""

    DEFAULT_PROFILE_NAME = "Default"

    @staticmethod
    def _normalize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(profile if isinstance(profile, dict) else {})
        out["name"] = str(out.get("name") or RestoreService.DEFAULT_PROFILE_NAME).strip() or RestoreService.DEFAULT_PROFILE_NAME
        out["open_folder"] = bool(out.get("open_folder", True))
        out["open_terminal"] = bool(out.get("open_terminal", True))
        out["open_vscode"] = bool(out.get("open_vscode", True))
        out["open_running_apps"] = bool(out.get("open_running_apps", False))
        out["show_checklist"] = bool(out.get("show_checklist", True))
        out["default"] = bool(out.get("default", False))
        return out

    def normalize_profiles(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen_names = set()
        for raw in profiles or []:
            profile = self._normalize_profile(raw)
            if profile["name"].lower() in seen_names:
                continue
            seen_names.add(profile["name"].lower())
            out.append(profile)
        if out and not any(p.get("default") for p in out):
            out[0]["default"] = True
        return out

    def default_restore_options(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        restore_cfg = settings.get("restore", {}) if isinstance(settings, dict) else {}
        defaults = {
            "open_folder": bool(restore_cfg.get("open_folder", True)),
            "open_terminal": bool(restore_cfg.get("open_terminal", True)),
            "open_vscode": bool(restore_cfg.get("open_vscode", True)),
            "open_running_apps": bool(restore_cfg.get("open_running_apps", False)),
            "show_checklist": bool(restore_cfg.get("show_post_restore_checklist", True)),
            "profile_name": "",
        }

        flags = settings.get("dev_flags", {}) if isinstance(settings, dict) else {}
        enabled = bool(flags.get("restore_profiles_enabled", False))
        if not enabled:
            return defaults

        profiles = self.normalize_profiles(settings.get("restore_profiles", []))
        if not profiles:
            return defaults

        profile = next((p for p in profiles if p.get("default")), profiles[0])
        defaults.update(
            {
                "open_folder": bool(profile.get("open_folder", True)),
                "open_terminal": bool(profile.get("open_terminal", True)),
                "open_vscode": bool(profile.get("open_vscode", True)),
                "open_running_apps": bool(profile.get("open_running_apps", False)),
                "show_checklist": bool(profile.get("show_checklist", True)),
                "profile_name": str(profile.get("name", "")),
            }
        )
        return defaults

    def apply_profile(self, settings: Dict[str, Any], profile_name: str, choices: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(choices)
        profiles = self.normalize_profiles(settings.get("restore_profiles", []))
        if not profiles:
            return out
        selected = next((p for p in profiles if p.get("name") == profile_name), None)
        if not selected:
            return out
        out["open_folder"] = bool(selected.get("open_folder", out.get("open_folder", True)))
        out["open_terminal"] = bool(selected.get("open_terminal", out.get("open_terminal", True)))
        out["open_vscode"] = bool(selected.get("open_vscode", out.get("open_vscode", True)))
        out["open_running_apps"] = bool(selected.get("open_running_apps", out.get("open_running_apps", False)))
        out["show_checklist"] = bool(selected.get("show_checklist", out.get("show_checklist", True)))
        out["profile_name"] = selected.get("name", "")
        return out

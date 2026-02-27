from __future__ import annotations

import base64
import ctypes
import json
import logging
from copy import deepcopy
from ctypes import wintypes
from typing import Any, Dict, Iterable, Optional, Tuple

from ctxsnap.constants import APP_NAME

LOGGER = logging.getLogger(APP_NAME)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class SecurityService:
    """Windows DPAPI-backed sensitive field encryption helpers."""

    ENVELOPE_VERSION = 1

    def __init__(self) -> None:
        self._crypt32 = None
        self._kernel32 = None
        if hasattr(ctypes, "windll"):
            try:
                self._crypt32 = ctypes.windll.crypt32
                self._kernel32 = ctypes.windll.kernel32
            except Exception:
                self._crypt32 = None
                self._kernel32 = None

    def is_available(self) -> bool:
        return self._crypt32 is not None and self._kernel32 is not None

    @staticmethod
    def _json_default(value: Any) -> Any:
        return str(value)

    @staticmethod
    def _make_blob(raw: bytes) -> Tuple[_DataBlob, Any]:
        if not raw:
            return _DataBlob(0, None), None
        buf = (ctypes.c_byte * len(raw))(*raw)
        return _DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf

    def _protect(self, raw: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("DPAPI unavailable")
        in_blob, in_buf = self._make_blob(raw)
        out_blob = _DataBlob()
        ok = self._crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        )
        _ = in_buf  # keep source buffer alive for the API call
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            self._kernel32.LocalFree(out_blob.pbData)

    def _unprotect(self, raw: bytes) -> bytes:
        if not self.is_available():
            raise RuntimeError("DPAPI unavailable")
        in_blob, in_buf = self._make_blob(raw)
        out_blob = _DataBlob()
        ok = self._crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        )
        _ = in_buf  # keep source buffer alive for the API call
        if not ok:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            self._kernel32.LocalFree(out_blob.pbData)

    def encrypt_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=self._json_default).encode("utf-8")
        enc = self._protect(raw)
        return {
            "enc": "dpapi",
            "v": self.ENVELOPE_VERSION,
            "blob": base64.b64encode(enc).decode("ascii"),
        }

    def decrypt_payload(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(envelope, dict):
            raise ValueError("Invalid encrypted payload")
        if envelope.get("enc") != "dpapi":
            raise ValueError("Unsupported envelope")
        blob = str(envelope.get("blob") or "").strip()
        if not blob:
            raise ValueError("Empty encrypted blob")
        raw = self._unprotect(base64.b64decode(blob.encode("ascii")))
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Decrypted payload is not dict")
        return data

    @staticmethod
    def _security_enabled(settings: Dict[str, Any]) -> bool:
        flags = settings.get("dev_flags", {}) if isinstance(settings, dict) else {}
        sec = settings.get("security", {}) if isinstance(settings, dict) else {}
        return bool(flags.get("security_enabled", False) and sec.get("dpapi_enabled", False))

    @staticmethod
    def _field_enabled(settings: Dict[str, Any], key: str, default: bool = True) -> bool:
        sec = settings.get("security", {}) if isinstance(settings, dict) else {}
        return bool(sec.get(key, default))

    def encrypt_snapshot_sensitive_fields(self, snap: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
        """Return a new snapshot dict with configured sensitive fields encrypted into `sensitive`."""
        out = deepcopy(snap)
        if not self._security_enabled(settings):
            return out
        if not self.is_available():
            raise RuntimeError("DPAPI unavailable")

        sensitive: Dict[str, Any] = {}
        if self._field_enabled(settings, "encrypt_note", True) and out.get("note"):
            sensitive["note"] = out.get("note", "")
            out["note"] = ""
        if self._field_enabled(settings, "encrypt_todos", True) and any(out.get("todos", [])):
            sensitive["todos"] = out.get("todos", [])
            out["todos"] = ["", "", ""]
        if self._field_enabled(settings, "encrypt_processes", True) and out.get("processes"):
            sensitive["processes"] = out.get("processes", [])
            out["processes"] = []
        if self._field_enabled(settings, "encrypt_running_apps", True) and out.get("running_apps"):
            sensitive["running_apps"] = out.get("running_apps", [])
            out["running_apps"] = []

        if sensitive:
            out["sensitive"] = self.encrypt_payload(sensitive)
        return out

    def decrypt_snapshot_sensitive_fields(self, snap: Dict[str, Any]) -> Dict[str, Any]:
        out = deepcopy(snap)
        envelope = out.get("sensitive")
        if not isinstance(envelope, dict) or envelope.get("enc") != "dpapi":
            return out
        try:
            sensitive = self.decrypt_payload(envelope)
        except Exception as exc:
            LOGGER.warning("security_decrypt failed: %s", exc)
            out.setdefault("_security_error", str(exc))
            return out

        if isinstance(sensitive.get("note"), str) and not out.get("note"):
            out["note"] = sensitive.get("note", "")
        if isinstance(sensitive.get("todos"), list) and not any(out.get("todos") or []):
            out["todos"] = [str(x) for x in sensitive.get("todos", [])][:3]
            while len(out["todos"]) < 3:
                out["todos"].append("")
        if isinstance(sensitive.get("processes"), list) and not out.get("processes"):
            out["processes"] = sensitive.get("processes", [])
        if isinstance(sensitive.get("running_apps"), list) and not out.get("running_apps"):
            out["running_apps"] = sensitive.get("running_apps", [])
        return out

    def encrypt_backup_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("DPAPI unavailable")
        return {
            "app": APP_NAME,
            "version": 3,
            "encrypted_backup": True,
            "payload": self.encrypt_payload(payload),
        }

    def decrypt_backup_payload(self, wrapped: Dict[str, Any]) -> Dict[str, Any]:
        envelope = wrapped.get("payload") if isinstance(wrapped, dict) else None
        if not isinstance(envelope, dict):
            raise ValueError("Invalid encrypted backup payload")
        return self.decrypt_payload(envelope)

    @staticmethod
    def copy_without_sensitive(snap: Dict[str, Any], keep_fields: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        keep = set(keep_fields or [])
        out = deepcopy(snap)
        if "sensitive" in out and "sensitive" not in keep:
            out.pop("sensitive", None)
        return out

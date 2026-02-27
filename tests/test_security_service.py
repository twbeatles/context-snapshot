from __future__ import annotations

import pytest

from ctxsnap.core.security import SecurityService


def _enabled_settings() -> dict:
    return {
        "dev_flags": {"security_enabled": True},
        "security": {
            "dpapi_enabled": True,
            "encrypt_note": True,
            "encrypt_todos": True,
            "encrypt_processes": True,
            "encrypt_running_apps": True,
        },
    }


def test_dpapi_roundtrip_payload() -> None:
    svc = SecurityService()
    if not svc.is_available():
        pytest.skip("DPAPI not available")
    payload = {"note": "hello", "todos": ["a", "b", "c"]}
    enc = svc.encrypt_payload(payload)
    dec = svc.decrypt_payload(enc)
    assert dec == payload


def test_encrypt_and_decrypt_snapshot_sensitive_fields() -> None:
    svc = SecurityService()
    if not svc.is_available():
        pytest.skip("DPAPI not available")
    snap = {
        "id": "s1",
        "note": "secret",
        "todos": ["one", "two", "three"],
        "processes": [{"name": "code"}],
        "running_apps": [{"name": "chrome"}],
    }
    encrypted = svc.encrypt_snapshot_sensitive_fields(snap, _enabled_settings())
    assert encrypted.get("sensitive", {}).get("enc") == "dpapi"
    assert encrypted["note"] == ""
    assert encrypted["todos"] == ["", "", ""]
    decrypted = svc.decrypt_snapshot_sensitive_fields(encrypted)
    assert decrypted["note"] == "secret"
    assert decrypted["todos"][0] == "one"

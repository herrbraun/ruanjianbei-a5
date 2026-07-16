from __future__ import annotations

import pytest

from scripts import init_admin


def test_initial_admin_credentials_require_a_strong_environment_password(monkeypatch) -> None:
    read_credentials = getattr(init_admin, "read_initial_admin_credentials", None)
    assert read_credentials is not None

    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_PASSWORD"):
        read_credentials()

    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "123456")
    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_PASSWORD"):
        read_credentials()

    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "replace-with-a-strong-admin-password")
    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_PASSWORD"):
        read_credentials()

    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "guide-admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "a-strong-demo-password")
    assert read_credentials() == ("guide-admin", "a-strong-demo-password")

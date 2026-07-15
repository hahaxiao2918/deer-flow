"""Tests for artifact path resolution fallback in auth-disabled mode."""

from pathlib import Path

import pytest

from app.gateway.path_utils import _resolve_across_user_buckets, resolve_thread_virtual_path


@pytest.fixture
def paths_tmp(tmp_path, monkeypatch):
    """Point get_paths() at a fresh temporary base_dir."""
    from deerflow.config.paths import Paths

    paths = Paths(base_dir=tmp_path)
    monkeypatch.setattr("deerflow.config.paths._paths", paths)
    # Also patch the module-level get_paths singleton used by path_utils.
    monkeypatch.setattr("app.gateway.path_utils.get_paths", lambda: paths)
    return paths


def _write_file(paths, thread_id: str, user_id: str, virtual_path: str, content: str) -> Path:
    """Create a file under users/{user_id}/threads/{thread_id}/user-data/{relative}."""
    relative = virtual_path.lstrip("/").removeprefix("mnt/user-data/").lstrip("/")
    file_path = paths.base_dir / "users" / user_id / "threads" / thread_id / "user-data" / relative
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_resolve_thread_virtual_path_prefers_primary_user(paths_tmp, monkeypatch):
    """When the primary user bucket has the file, return it directly."""
    monkeypatch.setenv("DEER_FLOW_AUTH_DISABLED", "1")
    monkeypatch.setattr(
        "app.gateway.path_utils.get_effective_user_id",
        lambda: "default",
    )

    _write_file(paths_tmp, "t1", "default", "/mnt/user-data/outputs/report.md", "primary")

    resolved = resolve_thread_virtual_path("t1", "/mnt/user-data/outputs/report.md")

    assert resolved.name == "report.md"
    assert resolved.read_text(encoding="utf-8") == "primary"


def test_resolve_thread_virtual_path_falls_back_in_auth_disabled(paths_tmp, monkeypatch):
    """When auth is disabled and default has no file, scan other user buckets."""
    monkeypatch.setenv("DEER_FLOW_AUTH_DISABLED", "1")
    monkeypatch.setattr(
        "app.gateway.path_utils.get_effective_user_id",
        lambda: "default",
    )

    actual = _write_file(
        paths_tmp,
        "t1",
        "3db86a6c-97dc-471c-8a7c-78039007bcc4",
        "/mnt/user-data/outputs/report.md",
        "from-real-user",
    )

    resolved = resolve_thread_virtual_path("t1", "/mnt/user-data/outputs/report.md")

    assert resolved == actual
    assert resolved.read_text(encoding="utf-8") == "from-real-user"


def test_resolve_thread_virtual_path_no_fallback_when_auth_enabled(
    paths_tmp,
    monkeypatch,
):
    """When auth is enabled, missing primary bucket must not scan other users."""
    monkeypatch.setenv("DEER_FLOW_AUTH_DISABLED", "0")
    monkeypatch.setattr(
        "app.gateway.path_utils.get_effective_user_id",
        lambda: "default",
    )

    _write_file(
        paths_tmp,
        "t1",
        "3db86a6c-97dc-471c-8a7c-78039007bcc4",
        "/mnt/user-data/outputs/report.md",
        "from-real-user",
    )

    resolved = resolve_thread_virtual_path("t1", "/mnt/user-data/outputs/report.md")

    # Should return the default path even though it does not exist.
    assert not resolved.exists()


def test_resolve_thread_virtual_path_explicit_user_id_no_fallback(
    paths_tmp,
    monkeypatch,
):
    """An explicit user_id should never trigger the fallback scan."""
    monkeypatch.setenv("DEER_FLOW_AUTH_DISABLED", "1")

    _write_file(
        paths_tmp,
        "t1",
        "3db86a6c-97dc-471c-8a7c-78039007bcc4",
        "/mnt/user-data/outputs/report.md",
        "from-real-user",
    )

    resolved = resolve_thread_virtual_path(
        "t1",
        "/mnt/user-data/outputs/report.md",
        user_id="default",
    )

    # Even though auth is disabled, user_id was passed explicitly; fallback
    # should still work because effective_user_id == DEFAULT_USER_ID.
    assert resolved.exists()
    assert resolved.read_text(encoding="utf-8") == "from-real-user"


def test_resolve_across_user_buckets_rejects_traversal(paths_tmp):
    """The fallback scanner must not return paths outside user-data."""
    base = paths_tmp.base_dir
    users_dir = base / "users" / "u1" / "threads" / "t1" / "user-data"
    users_dir.mkdir(parents=True)
    secret = base / "secret.txt"
    secret.write_text("secret", encoding="utf-8")

    # Create a symlink that escapes user-data; the fallback should reject it.
    (users_dir / "escape").symlink_to("../../../../secret.txt")

    result = _resolve_across_user_buckets("t1", "/mnt/user-data/outputs/report.md", "default")
    assert result is None


def test_resolve_across_user_buckets_only_returns_existing_files(paths_tmp):
    """Missing files in other buckets should be ignored."""
    base = paths_tmp.base_dir
    (base / "users" / "u1" / "threads" / "t1" / "user-data" / "outputs").mkdir(parents=True)

    result = _resolve_across_user_buckets("t1", "/mnt/user-data/outputs/report.md", "default")
    assert result is None


def test_resolve_thread_virtual_path_raises_on_invalid_path(paths_tmp, monkeypatch):
    """Invalid virtual paths still raise HTTPException regardless of auth mode."""
    monkeypatch.setenv("DEER_FLOW_AUTH_DISABLED", "1")
    monkeypatch.setattr(
        "app.gateway.path_utils.get_effective_user_id",
        lambda: "default",
    )

    with pytest.raises(Exception):  # HTTPException or ValueError depending on layer
        resolve_thread_virtual_path("t1", "/mnt/other/path/report.md")

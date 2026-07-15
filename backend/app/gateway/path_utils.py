"""Shared path resolution for thread virtual paths (e.g. mnt/user-data/outputs/...)."""

from pathlib import Path

from fastapi import HTTPException

from deerflow.config.paths import VIRTUAL_PATH_PREFIX, get_paths
from deerflow.runtime.user_context import DEFAULT_USER_ID, get_effective_user_id

from .auth_disabled import is_auth_disabled


def _resolve_for_user(thread_id: str, virtual_path: str, user_id: str) -> Path:
    """Resolve virtual_path for a specific user_id.

    Does not check existence. Re-raises ValueError for invalid/traversal paths.
    """
    return get_paths().resolve_virtual_path(thread_id, virtual_path, user_id=user_id)


def _resolve_across_user_buckets(
    thread_id: str,
    virtual_path: str,
    preferred_user_id: str,
) -> Path | None:
    """Find an existing resolution across user buckets.

    Used in auth-disabled mode: the effective user is ``DEFAULT_USER_ID``
    (``"default"``), but threads and their files may have been created under a
    real user bucket. Walk every ``users/{user_id}/threads/{thread_id}``
    directory and return the first one where the resolved virtual path exists.
    """
    base_dir = get_paths().base_dir
    users_dir = base_dir / "users"
    if not users_dir.is_dir():
        return None

    relative = virtual_path.lstrip("/")
    prefix = VIRTUAL_PATH_PREFIX.lstrip("/")
    if relative != prefix and not relative.startswith(prefix + "/"):
        return None
    relative_within_user_data = relative[len(prefix) :].lstrip("/")

    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir():
            continue
        candidate_user_id = user_dir.name
        if candidate_user_id == preferred_user_id:
            continue
        thread_dir = user_dir / "threads" / thread_id
        if not thread_dir.is_dir():
            continue
        candidate = (thread_dir / "user-data" / relative_within_user_data).resolve()
        try:
            candidate.relative_to(thread_dir / "user-data")
        except ValueError:
            continue
        if candidate.exists():
            return candidate
    return None


def resolve_thread_virtual_path(thread_id: str, virtual_path: str, user_id: str | None = None) -> Path:
    """Resolve a virtual path to the actual filesystem path under thread user-data.

    Args:
        thread_id: The thread ID.
        virtual_path: The virtual path as seen inside the sandbox
                      (e.g., /mnt/user-data/outputs/file.txt).
        user_id: The user whose storage to resolve under. Defaults to the
                 effective user when not given; callers acting on behalf of a
                 specific owner (e.g. trusted internal callers) pass it explicitly.

    Returns:
        The resolved filesystem path.

    Raises:
        HTTPException: If the path is invalid or outside allowed directories.
    """
    effective_user_id = user_id or get_effective_user_id()
    try:
        primary = _resolve_for_user(thread_id, virtual_path, effective_user_id)
    except ValueError as e:
        status = 403 if "traversal" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e)) from e

    if primary.exists():
        return primary

    # Auth-disabled mode: threads may have been created under a real user bucket
    # while the current request runs as the synthetic default user. Fall back to
    # scanning other user buckets for the same thread and virtual path. This is
    # safe because auth-disabled is explicitly local-only and documented as such.
    if effective_user_id == DEFAULT_USER_ID and is_auth_disabled():
        fallback = _resolve_across_user_buckets(thread_id, virtual_path, effective_user_id)
        if fallback is not None:
            return fallback

    return primary

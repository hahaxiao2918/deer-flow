"""Tests for inlining local media paths as data URLs for remote MCP tools."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import ToolException

from deerflow.mcp import tools as tools_module
from deerflow.mcp.tools import (
    _convert_local_media_to_data_url,
    _is_local_media_path,
    _make_remote_media_tool,
    _make_session_pool_tool,
    _maybe_inline_local_media_argument,
    _maybe_inline_local_media_arguments,
    _resolve_local_media_path,
)


@pytest.fixture
def user_data_prefix(tmp_path: Path) -> str:
    """Point the user-data prefix at the temporary directory for tests."""
    prefix = str(tmp_path) + "/"
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(tools_module, "_USER_DATA_PREFIX", prefix)
        yield prefix


@pytest.fixture
def tiny_png(user_data_prefix: str) -> str:
    """Create a tiny valid PNG under the fake user-data prefix."""
    path = Path(user_data_prefix) / "uploads" / "image.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    # 1x1 transparent PNG bytes
    data = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c630000000100010518d84d0000000049454e44ae426082")
    path.write_bytes(data)
    return str(path)


@pytest.fixture
def tiny_mp4(user_data_prefix: str) -> str:
    """Create a tiny file with .mp4 extension under the fake prefix."""
    path = Path(user_data_prefix) / "uploads" / "clip.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x20ftypisom")
    return str(path)


@pytest.fixture
def text_file(user_data_prefix: str) -> str:
    """Create a non-media file under the fake prefix."""
    path = Path(user_data_prefix) / "uploads" / "notes.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("hello")
    return str(path)


@pytest.fixture
def oversized_png(user_data_prefix: str) -> str:
    """Create a PNG-looking file over the 4 MiB inline limit."""
    path = Path(user_data_prefix) / "uploads" / "big.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"a" * (4 * 1024 * 1024 + 1))
    return str(path)


class TestIsLocalMediaPath:
    def test_accepts_local_image_path(self, tiny_png: str):
        assert _is_local_media_path(tiny_png) is True

    def test_accepts_local_video_path(self, tiny_mp4: str):
        assert _is_local_media_path(tiny_mp4) is True

    def test_rejects_http_url(self):
        assert _is_local_media_path("https://example.com/img.png") is False

    def test_rejects_data_url(self):
        assert _is_local_media_path("data:image/png;base64,abcd") is False

    def test_rejects_non_media_local_file(self, text_file: str):
        assert _is_local_media_path(text_file) is False

    def test_rejects_non_existent_file(self, user_data_prefix: str):
        assert _is_local_media_path(f"{user_data_prefix}uploads/missing.png") is False

    def test_rejects_paths_outside_user_data(self, tiny_png: str):
        # Same filename but outside the configured prefix.
        outside = "/elsewhere/uploads/image.png"
        assert _is_local_media_path(outside) is False

    def test_resolves_virtual_path_inside_current_thread(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        user_data = tmp_path / "users" / "user-1" / "threads" / "thread-1" / "user-data"
        image = user_data / "uploads" / "image.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"png")

        paths = MagicMock()
        paths.sandbox_user_data_dir.return_value = user_data
        monkeypatch.setattr(tools_module, "get_paths", lambda: paths)

        assert _resolve_local_media_path("/mnt/user-data/uploads/image.png", thread_id="thread-1", user_id="user-1") == image

    def test_rejects_virtual_path_escaping_current_thread(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        user_data = tmp_path / "user-data"
        user_data.mkdir()
        paths = MagicMock()
        paths.sandbox_user_data_dir.return_value = user_data
        monkeypatch.setattr(tools_module, "get_paths", lambda: paths)

        assert _resolve_local_media_path("/mnt/user-data/../outside.png", thread_id="thread-1", user_id="user-1") is None


class TestConvertLocalMediaToDataUrl:
    def test_produces_correct_data_url(self, tiny_png: str):
        result = _convert_local_media_to_data_url(tiny_png)
        assert result.startswith("data:image/png;base64,")
        payload = result.split(",", 1)[1]
        assert base64.b64decode(payload) == Path(tiny_png).read_bytes()


class TestMaybeInlineLocalMediaArgument:
    def test_converts_local_image_path(self, tiny_png: str):
        result = _maybe_inline_local_media_argument(tiny_png)
        assert result.startswith("data:image/png;base64,")

    def test_converts_local_video_path(self, tiny_mp4: str):
        result = _maybe_inline_local_media_argument(tiny_mp4)
        assert result.startswith("data:video/mp4;base64,")

    def test_leaves_http_url_unchanged(self):
        url = "https://example.com/img.png"
        assert _maybe_inline_local_media_argument(url) == url

    def test_leaves_data_url_unchanged(self):
        url = "data:image/png;base64,abcd"
        assert _maybe_inline_local_media_argument(url) == url

    def test_leaves_non_media_path_unchanged(self, text_file: str):
        assert _maybe_inline_local_media_argument(text_file) == text_file

    def test_leaves_oversized_image_unchanged(self, oversized_png: str):
        assert _maybe_inline_local_media_argument(oversized_png) == oversized_png

    def test_rejects_oversized_image_when_remote_call_requires_inlining(self, oversized_png: str):
        with pytest.raises(ToolException, match="maximum 4194304 bytes"):
            _maybe_inline_local_media_argument(oversized_png, reject_oversized=True)

    def test_recursively_converts_nested_arguments(self, tiny_png: str):
        args = {
            "image_source": tiny_png,
            "nested": {"inner": [tiny_png]},
            "prompt": "describe",
        }
        result = _maybe_inline_local_media_arguments(args)
        assert result["image_source"].startswith("data:image/png;base64,")
        assert result["nested"]["inner"][0].startswith("data:image/png;base64,")
        assert result["prompt"] == "describe"

    def test_preserves_non_string_values(self, tiny_png: str):
        args = {
            "count": 42,
            "flag": True,
            "none": None,
            "image_source": "https://example.com/img.png",
        }
        result = _maybe_inline_local_media_arguments(args)
        assert result["count"] == 42
        assert result["flag"] is True
        assert result["none"] is None
        assert result["image_source"] == "https://example.com/img.png"


class _FakeTool:
    """Captures the coroutine from StructuredTool so we can invoke it directly."""

    def __init__(self, **kwargs):
        self.coroutine = kwargs["coroutine"]

    async def ainvoke(self, args, **_kwargs):
        return await self.coroutine(**args)


class _OriginalRemoteTool:
    """Minimal HTTP MCP-like tool for asserting wrapper call arguments."""

    name = "zai-mcp-server_analyze_image"
    description = "analyze an image"
    args_schema = None
    response_format = "content_and_artifact"
    metadata = {"deerflow_mcp": True}

    def __init__(self):
        self.coroutine = AsyncMock(return_value=([{"type": "text", "text": "ok"}], None))
        self.ainvoke = AsyncMock(return_value=[{"type": "text", "text": "ok"}])


@pytest.mark.asyncio
async def test_make_session_pool_tool_inlines_media_for_http_transport(tiny_png: str):
    """Remote HTTP MCP calls have local image paths inlined before call_tool."""
    mock_session = AsyncMock()

    with patch("deerflow.mcp.tools.StructuredTool", _FakeTool), patch("deerflow.mcp.tools.get_session_pool") as mock_get_pool, patch("deerflow.mcp.tools._convert_call_tool_result", return_value=([], None)):
        mock_pool = MagicMock()
        mock_pool.get_session = AsyncMock(return_value=mock_session)
        mock_get_pool.return_value = mock_pool

        tool = MagicMock()
        tool.name = "zai-mcp-server_analyze_image"

        wrapped = _make_session_pool_tool(
            tool,
            server_name="zai-mcp-server",
            connection={"transport": "http", "url": "http://example.com/mcp"},
        )

        await wrapped.ainvoke({"image_source": tiny_png, "prompt": "describe"})

    mock_session.call_tool.assert_awaited_once()
    call_name, call_args = mock_session.call_tool.call_args[0]
    assert call_name == "analyze_image"
    assert call_args["image_source"].startswith("data:image/png;base64,")
    assert call_args["prompt"] == "describe"


@pytest.mark.asyncio
async def test_remote_media_tool_inlines_media_without_http_session_pool(tiny_png: str):
    """The production HTTP/SSE wrapper forwards a data URL to the original tool."""
    original = _OriginalRemoteTool()
    with patch("deerflow.mcp.tools.StructuredTool", _FakeTool):
        wrapped = _make_remote_media_tool(original)
        result = await wrapped.ainvoke({"image_source": tiny_png, "prompt": "describe"})

    assert result == ([{"type": "text", "text": "ok"}], None)
    original.ainvoke.assert_not_awaited()
    original.coroutine.assert_awaited_once()
    call_args = original.coroutine.call_args.kwargs
    assert call_args["image_source"].startswith("data:image/png;base64,")
    assert call_args["prompt"] == "describe"


@pytest.mark.asyncio
async def test_remote_media_tool_rejects_oversized_media_before_call(oversized_png: str):
    original = _OriginalRemoteTool()
    with patch("deerflow.mcp.tools.StructuredTool", _FakeTool):
        wrapped = _make_remote_media_tool(original)
        with pytest.raises(ToolException, match="maximum 4194304 bytes"):
            await wrapped.ainvoke({"image_source": oversized_png, "prompt": "describe"})

    original.coroutine.assert_not_awaited()


@pytest.mark.asyncio
async def test_make_session_pool_tool_preserves_paths_for_stdio_transport(tmp_path: Path):
    """Local stdio MCP calls keep local paths unchanged."""
    image_path = tmp_path / "uploads" / "image.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake png")

    mock_session = AsyncMock()

    with (
        patch("deerflow.mcp.tools.StructuredTool", _FakeTool),
        patch("deerflow.mcp.tools.get_session_pool") as mock_get_pool,
        patch("deerflow.mcp.tools.get_paths"),
        patch("deerflow.mcp.tools._prepare_stdio_workspace", return_value=(tmp_path, tmp_path, None)),
        patch("deerflow.mcp.tools._convert_call_tool_result", return_value=([], None)),
    ):
        mock_pool = MagicMock()
        mock_pool.get_session = AsyncMock(return_value=mock_session)
        mock_get_pool.return_value = mock_pool

        tool = MagicMock()
        tool.name = "local_analyze_image"

        wrapped = _make_session_pool_tool(
            tool,
            server_name="local",
            connection={"transport": "stdio", "command": "node", "args": ["server.js"]},
        )

        await wrapped.ainvoke({"image_source": str(image_path), "prompt": "describe"})

    _name, call_args = mock_session.call_tool.call_args[0]
    assert call_args["image_source"] == str(image_path)

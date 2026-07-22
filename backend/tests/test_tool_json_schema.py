"""Regression: every builtin tool's argument schema must be JSON-schema-generatable.

Tools are converted to OpenAI function specs (a JSON schema) on every model call so
the LLM knows their parameters. A tool whose args surface a non-JSON-serializable
type raises ``PydanticInvalidForJsonSchema`` at bind time and breaks every chat turn.

This was introduced for ``list_uploaded_files`` by upstream PR #4174, which declared
its injected runtime as ``Annotated[Runtime, InjectedToolArg] | None = None``. The
``| None`` union defeats langchain 1.x's ``ToolRuntime`` marker short-circuit, so
pydantic introspects the marker class itself and hits ``ToolRuntime.stream_writer``
(a ``Callable`` → ``core_schema.CallableSchema``), which has no JSON representation.
The fix is the official pattern every other builtin tool already uses:
``runtime: Runtime`` as the first parameter.

This test locks the invariant for every builtin tool so a future upstream sync
cannot silently reintroduce the same class of defect.
"""

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from deerflow.tools import builtins


@pytest.mark.parametrize("name", builtins.__all__)
def test_builtin_tool_args_schema_is_json_generatable(name: str) -> None:
    """Each builtin tool must produce a valid OpenAI function parameter schema."""
    tool = getattr(builtins, name)
    # This is the exact conversion that runs when tools are bound to a chat model.
    spec = convert_to_openai_tool(tool)
    params = spec["function"]["parameters"]
    assert isinstance(params, dict)
    assert params.get("type") == "object"


def test_list_uploaded_files_hides_runtime_from_schema() -> None:
    """The injected ``runtime`` must never leak into the LLM-visible schema.

    Pinning ``list_uploaded_files`` specifically: it is the tool whose upstream
    annotation (#4174) triggered the CallableSchema failure, so it deserves a
    dedicated guard in addition to the parametrized loop above.
    """
    from deerflow.tools.builtins.list_uploaded_files_tool import list_uploaded_files

    spec = convert_to_openai_tool(list_uploaded_files)
    properties = spec["function"]["parameters"].get("properties", {})
    assert "runtime" not in properties
    # The user-facing parameters are unchanged.
    assert set(properties) == {"include_outline", "max_results"}

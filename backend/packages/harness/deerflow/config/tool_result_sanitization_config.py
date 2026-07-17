"""Configuration for neutralizing untrusted remote tool-result content."""

from pydantic import BaseModel, Field


class ToolResultSanitizationConfig(BaseModel):
    """Additional MCP/tool name prefixes whose text is untrusted."""

    untrusted_tool_prefixes: list[str] = Field(
        default_factory=list,
        description="Tool-name prefixes whose returned text receives framework-tag neutralization",
    )

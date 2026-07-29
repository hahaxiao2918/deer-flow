"""Kimi Code adapter and DeerFlow-to-K3 effort mapping.

K3 accepts ``low``, ``high`` and ``max``.  DeerFlow's shared console uses
``minimal``, ``low``, ``medium`` and ``high``; this adapter makes those values
safe for K3 without changing the generic provider path.  Flash always maps to
``none``, allowing Kimi to route the request to K2.6.
"""

from langchain_openai import ChatOpenAI


class PatchedChatKimi(ChatOpenAI):
    """OpenAI-compatible Kimi Code client with K3 effort normalization."""

    @staticmethod
    def resolve_reasoning_effort(*, thinking_enabled: bool, effort: str | None) -> str:
        """Translate DeerFlow's shared effort names to K3's supported values."""
        if not thinking_enabled:
            return "none"
        return {
            "minimal": "low",
            "minimum": "low",
            "low": "low",
            "medium": "high",
            # DeerFlow has no xhigh option. Its highest visible choice maps to
            # K3's highest supported effort.
            "high": "max",
            "ultra": "max",
            "xhigh": "max",
            "max": "max",
            "none": "none",
        }.get(effort or "", "high")

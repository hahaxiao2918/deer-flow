"""Kimi Code adapter for DeerFlow's hidden reasoning-effort UI policy.

Kimi Code accepts ``reasoning_effort=high`` for K3 thinking and
``reasoning_effort=none`` to disable thinking (which lets Kimi route K3 flash
requests to K2.6).  DeerFlow deliberately hides the generic effort picker for
this provider, so the factory must retain these profile-owned values while it
still drops any request-supplied generic effort.
"""

from typing import ClassVar

from langchain_openai import ChatOpenAI


class PatchedChatKimi(ChatOpenAI):
    """OpenAI-compatible Kimi Code client with profile-owned effort settings."""

    preserve_hidden_reasoning_effort: ClassVar[bool] = True

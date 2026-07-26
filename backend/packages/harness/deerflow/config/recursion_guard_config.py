"""Configuration for the recursion guard middleware.

Mirrors :class:`~deerflow.config.loop_detection_config.LoopDetectionConfig`:
defaults live here, the lead agent reads the instance from
``AppConfig.recursion_guard`` and constructs the middleware via
``RecursionGuardMiddleware.from_config``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecursionGuardConfig(BaseModel):
    """Recursion guard middleware configuration.

    The guard converts LangGraph's hard ``GraphRecursionError`` (raised when a
    run exceeds ``recursion_limit`` super-steps) into a natural finish: it
    injects a wrap-up reminder at ``warn_ratio * limit`` estimated steps and
    strips ``tool_calls`` at ``limit - hard_margin`` so the agent terminates
    with a final answer instead of an exception.
    """

    enabled: bool = Field(
        default=True,
        description="Whether the recursion guard middleware is active. Disable to restore the raw GraphRecursionError behaviour.",
    )
    warn_ratio: float = Field(
        default=0.75,
        gt=0.0,
        lt=1.0,
        description="Fraction of the run's recursion_limit at which a wrap-up reminder is injected (e.g. 0.75 of 100 -> warn around step 75).",
    )
    hard_margin: int = Field(
        default=10,
        ge=1,
        description="Hard-stop margin: tool_calls are stripped at ``limit - hard_margin`` estimated steps (never below warn+1). The effective margin is ``max(hard_margin, chain_hook_nodes + 4)`` so the post-strip tail (remaining after_model hook nodes in the same cycle + END routing) always fits before LangGraph's hard error.",
    )

"""
LangChain adapter for Action Marshall.

Status: **experimental**. The LangChain API surface has changed several
times; we currently target ``langchain-core >= 0.1`` (the ``BaseTool``
class lives in ``langchain_core.tools``). If you are on an older
LangChain version, wrap the underlying ``_run`` callable manually via
``ks.wrap_function(...)`` instead.

Usage:

    from langchain_core.tools import tool
    from action_marshall import MarshallClient
    from action_marshall.adapters.langchain import wrap_langchain_tool

    @tool
    def update_incident(payload: dict) -> dict:
        # ... your tool ...
        return {"ok": True}

    ks = MarshallClient(api_key="...", base_url="http://localhost:8000")

    protected = wrap_langchain_tool(
        update_incident,
        ks=ks,
        tool="servicenow",
        action_type="update_incident",
        connector="servicenow_sim",
        agent_id="incident-agent",
    )

    # Every call to protected.invoke({...}) is now governed.
"""
from __future__ import annotations

from typing import Any

try:
    from langchain_core.tools import BaseTool  # type: ignore
except ImportError as e:  # pragma: no cover - exercised by the test, not by runtime
    raise ImportError(
        "Install Action Marshall with LangChain support: "
        "pip install 'action-marshall[langchain]'"
    ) from e

from action_marshall.client import MarshallClient


def wrap_langchain_tool(
    tool_obj: "BaseTool",
    *,
    ks: MarshallClient,
    tool: str,
    action_type: str,
    connector: str = "servicenow_sim",
    agent_id: str = "agent-001",
    **wrap_kwargs: Any,
) -> "BaseTool":
    """
    Wrap a LangChain ``BaseTool`` so every invocation is governed.

    Returns the same tool object with its ``_run`` method replaced by a
    Action Marshall-governed wrapper. The tool's name, description, schema, and
    LangChain-side behavior are preserved — only the execution path is
    intercepted.

    Args:
        tool_obj: A LangChain ``BaseTool`` instance.
        ks: A configured ``MarshallClient``.
        tool: Logical tool name (e.g. ``"servicenow"``).
        action_type: Logical action type (e.g. ``"update_incident"``).
        connector: Backend connector to evaluate against.
        agent_id: ID of the agent making the call.
        **wrap_kwargs: Passed to ``ks.wrap_function``.

    Raises:
        ImportError: ``langchain-core`` is not installed.
        TypeError: ``tool_obj`` is not a LangChain ``BaseTool``.
    """
    if not isinstance(tool_obj, BaseTool):
        raise TypeError(
            f"Expected a langchain_core.tools.BaseTool, got {type(tool_obj).__name__}. "
            f"For plain callables use ks.wrap_function() instead."
        )

    original_run = tool_obj._run
    wrapped = ks.wrap_function(
        original_run,
        tool=tool,
        action_type=action_type,
        connector=connector,
        agent_id=agent_id,
        **wrap_kwargs,
    )

    # LangChain's BaseTool is a Pydantic model; mutating private attrs is
    # supported because _run is not a field.
    object.__setattr__(tool_obj, "_run", wrapped)
    return tool_obj


__all__ = ["wrap_langchain_tool"]

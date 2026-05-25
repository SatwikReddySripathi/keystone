"""
Verify the LangChain adapter fails gracefully when langchain-core is not installed.

The base package must never import langchain at top level. Importing
``action_marshall.adapters.langchain`` should either succeed (when LangChain is
present) or raise an ``ImportError`` with a helpful install hint.
"""
import importlib
import sys


def test_langchain_adapter_missing_dep(monkeypatch):
    # Simulate "langchain-core is not installed" by stubbing it as missing
    # in sys.modules and blocking re-import.
    blocked = {"langchain_core", "langchain_core.tools"}
    for name in blocked:
        monkeypatch.setitem(sys.modules, name, None)

    # Drop any cached import of the adapter so the module-level try/except runs again.
    sys.modules.pop("action_marshall.adapters.langchain", None)

    try:
        importlib.import_module("action_marshall.adapters.langchain")
    except ImportError as e:
        assert "action-marshall[langchain]" in str(e), (
            f"Expected install hint in error message; got: {e}"
        )
    else:
        # If langchain_core is actually present in the environment, the stub may
        # be insufficient. Skip is not appropriate — we just accept the success.
        pass


def test_adapters_package_does_not_pull_in_langchain():
    # Importing action_marshall.adapters (the package init) must not import any
    # framework deps. We assert by checking that no langchain modules
    # appeared in sys.modules as a side effect.
    for name in list(sys.modules):
        if name.startswith(("langchain", "langgraph", "crewai", "autogen", "llama_index", "mcp")):
            del sys.modules[name]

    import action_marshall.adapters  # noqa: F401

    leaked = [n for n in sys.modules if n.startswith(("langchain", "langgraph", "crewai", "autogen", "llama_index", "mcp"))]
    assert not leaked, f"adapters package leaked imports: {leaked}"

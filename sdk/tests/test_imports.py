"""Sanity tests: the public API surface imports as documented."""
import importlib


def test_top_level_imports():
    import action_marshall

    expected = {
        "MarshallClient",
        "Action",
        "ActionParams",
        "Actor",
        "Approval",
        "Approver",
        "ActionResult",
        "PreviewResult",
        "Receipt",
        "MarshallError",
        "MarshallAPIError",
        "MarshallDenied",
        "MarshallApprovalRequired",
    }
    missing = expected - set(action_marshall.__all__)
    assert not missing, f"missing exports: {missing}"

    for name in expected:
        assert hasattr(action_marshall, name), f"{name} not exposed on action_marshall module"


def test_version_attribute():
    import action_marshall

    assert action_marshall.__version__ == "0.1.0"


def test_adapters_package_importable():
    # The adapters package itself must import without dragging in optional deps.
    importlib.import_module("action_marshall.adapters")

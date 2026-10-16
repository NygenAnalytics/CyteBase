"""The published SDK depends on CyteArc's public API, with listed exceptions.

``cytebase`` supports every CyteArc release that ``pyproject.toml`` admits, so
a CyteArc module that the SDK imports must stay importable across them. Public
names come from a CyteArc facade's ``__all__``. Every other CyteArc import is
listed in ``PRIVATE_CYTEARC_IMPORTS`` with its reason, and this test fails when
CyteArc no longer provides one. The Modal pipeline in ``cytebase/pipeline`` is
not published and runs against the CyteArc version that ``uv.lock`` pins, so
it may use CyteArc internals.
"""

import ast
import importlib
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "cytebase"
PUBLIC_FACADES = frozenset(
    {
        "cytearc",
        "cytearc.composite",
        "cytearc.plotting",
        "cytearc.storage",
        "cytearc.utils",
    }
)
PRIVATE_CYTEARC_IMPORTS = {
    # CyteArc has no public accessor for the progress setting that
    # cytearc.configure_output records; catalog queries follow it.
    ("catalog.py", "cytearc.utils.logging", "progress_enabled"),
    # Published stores open through CyteArc's cached, rate-limit-aware reader,
    # which the connector closes itself when opening fails.
    ("connector.py", "cytearc.storage.huggingface", "HfReadStore"),
    # Embedding coordinates follow the artifact's frozen cell selection.
    ("_embeddings.py", "cytearc.storage.selections", "read_stored_selection_indices"),
    ("_embeddings.py", "cytearc.storage.types", "as_zarr_array"),
}


def _sdk_modules() -> list[Path]:
    return sorted(
        path
        for path in PACKAGE.rglob("*.py")
        if "pipeline" not in path.relative_to(PACKAGE).parts
        and path.name != "_version.py"
    )


def _cytearc_imports(path: Path) -> set[tuple[str, str, str]]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "cytearc":
                    found.add((path.name, alias.name, ""))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] == "cytearc":
                for alias in node.names:
                    found.add((path.name, node.module, alias.name))
    return found


def _private_imports() -> set[tuple[str, str, str]]:
    private = set()
    for path in _sdk_modules():
        for file_name, module, name in _cytearc_imports(path):
            if module in PUBLIC_FACADES and name:
                facade = importlib.import_module(module)
                if name in facade.__all__:
                    continue
            private.add((file_name, module, name))
    return private


def test_sdk_imports_only_public_or_listed_cytearc_names():
    assert _private_imports() == PRIVATE_CYTEARC_IMPORTS


@pytest.mark.parametrize(
    "module, name", sorted({entry[1:] for entry in PRIVATE_CYTEARC_IMPORTS})
)
def test_listed_cytearc_internals_still_exist(module, name):
    assert hasattr(importlib.import_module(module), name)


def test_sdk_modules_do_not_import_the_unpublished_pipeline():
    for path in _sdk_modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not (node.level and module.split(".")[0] == "pipeline"), path
                assert not module.startswith("cytebase.pipeline"), path
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("cytebase.pipeline"), path

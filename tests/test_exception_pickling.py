"""CyteBase exceptions survive pickling, as process pools and Modal results need."""

import ast
import builtins
import pickle
from collections.abc import Callable
from pathlib import Path

import pytest

from cytebase.pipeline.resources import ImportMemoryRefusal

PACKAGE = Path(__file__).resolve().parents[1] / "cytebase"

SAMPLES: dict[type[BaseException], Callable[[], BaseException]] = {
    ImportMemoryRefusal: lambda: ImportMemoryRefusal("The layout needs 8 GB"),
}

_BUILTIN_EXCEPTIONS = frozenset(
    name
    for name, value in vars(builtins).items()
    if isinstance(value, type) and issubclass(value, BaseException)
)


def _name(error_type: type[BaseException]) -> str:
    return f"{error_type.__module__}.{error_type.__qualname__}"


def _base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Subscript):
        base = base.value
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _defined_exception_names() -> set[str]:
    """Return the qualified names of the exception classes CyteBase defines.

    The sources are parsed rather than imported, so pipeline modules are found
    where their dependency group is not installed.
    """
    classes: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = ("cytebase", *path.relative_to(PACKAGE).with_suffix("").parts)
        module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.ClassDef):
                classes[f"{module}.{node.name}"] = {
                    name for base in node.bases if (name := _base_name(base))
                }
    exception_bases = set(_BUILTIN_EXCEPTIONS)
    found: set[str] = set()
    while True:
        added = {
            name
            for name, bases in classes.items()
            if name not in found
            and any(
                base in exception_bases
                or base.endswith(("Error", "Exception", "Warning"))
                for base in bases
            )
        }
        if not added:
            return found
        found |= added
        exception_bases |= {name.rsplit(".", 1)[-1] for name in added}


def test_every_exception_class_has_a_pickling_sample() -> None:
    defined = _defined_exception_names()
    sampled = {_name(error_type) for error_type in SAMPLES}

    assert not sorted(defined - sampled), "Add a sample to SAMPLES"
    assert not sorted(sampled - defined), "Remove samples of classes no module defines"


@pytest.mark.parametrize("error_type", list(SAMPLES), ids=_name)
def test_exception_survives_a_pickle_round_trip(
    error_type: type[BaseException],
) -> None:
    error = SAMPLES[error_type]()
    assert type(error) is error_type
    error.add_note("Recorded while the run cleaned up")

    restored = pickle.loads(pickle.dumps(error))

    assert type(restored) is error_type
    assert restored.args == error.args
    assert str(restored) == str(error)
    assert vars(restored) == vars(error)

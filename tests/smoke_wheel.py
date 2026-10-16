"""Check a built CyteBase wheel, then install it in a clean environment and import it.

Run as ``uv run --no-project python tests/smoke_wheel.py dist/*.whl``. The wheel
must be pure Python, carry every SDK module, and leave out the Modal build
pipeline in ``cytebase/pipeline``, which runs from a checkout.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from email.parser import Parser
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

_PURE_TAG = "py3-none-any"
_SOURCE_ROOT = Path(__file__).resolve().parents[1] / "cytebase"
_REQUIRED_MODULES = {
    f"cytebase/{path.relative_to(_SOURCE_ROOT).as_posix()}"
    for path in _SOURCE_ROOT.rglob("*.py")
    if "pipeline" not in path.relative_to(_SOURCE_ROOT).parts
    and path.name != "_version.py"
}
_SMOKE_CODE = """
import importlib.metadata
import importlib.util
from pathlib import Path

from packaging.version import Version

import cytearc
import cytebase
from cytebase.display import CatalogResults

assert "site-packages" in Path(cytebase.__file__).as_posix()
assert importlib.util.find_spec("cytebase.pipeline") is None
assert set(cytebase.__all__) == {
    "Catalog",
    "DatasetEntry",
    "Release",
    "embedding",
    "embedding_coordinates",
    "embeddings",
    "releases",
}
for name in cytebase.__all__:
    assert getattr(cytebase, name) is not None, name
assert any(release.latest for release in cytebase.releases())
assert issubclass(CatalogResults, list)
assert Version(importlib.metadata.version("cytearc")) >= Version("1.1.0")
assert callable(cytearc.mount_datastore)
"""


def _wheel_tag_problems(wheel: Path, archive: ZipFile) -> list[str]:
    problems: list[str] = []
    file_tag = "-".join(wheel.name.removesuffix(".whl").split("-")[-3:])
    if file_tag != _PURE_TAG:
        problems.append(f"file name tag {file_tag!r}, expected {_PURE_TAG!r}")
    wheel_files = [
        name
        for name in archive.namelist()
        if len(PurePosixPath(name).parts) == 2
        and PurePosixPath(name).parts[0].endswith(".dist-info")
        and PurePosixPath(name).name == "WHEEL"
    ]
    if len(wheel_files) != 1:
        problems.append("the wheel must contain exactly one .dist-info/WHEEL file")
        return problems
    metadata = Parser().parsestr(archive.read(wheel_files[0]).decode("utf-8"))
    tags = [str(tag).strip() for tag in metadata.get_all("Tag") or []]
    if tags != [_PURE_TAG]:
        problems.append(f"WHEEL tags {tags}, expected [{_PURE_TAG!r}]")
    return problems


def validate_wheel_contents(wheel: Path) -> None:
    """Check that ``wheel`` holds the SDK modules and no pipeline or data files."""
    with ZipFile(wheel) as archive:
        names = set(archive.namelist())
        problems = _wheel_tag_problems(wheel, archive)
    for name in sorted(names):
        parts = PurePosixPath(name).parts
        if parts[0].endswith(".data"):
            problems.append(f"{name} is install-time data outside the import root")
        if parts[:2] == ("cytebase", "pipeline"):
            problems.append(f"{name} belongs to the unpublished build pipeline")
    missing = sorted(_REQUIRED_MODULES.difference(names))
    if missing:
        problems.append(f"required modules are missing: {missing}")
    if problems:
        raise RuntimeError(
            "\n".join(
                ["Wheel contents violate the published SDK contract:"]
                + [f"- {problem}" for problem in problems]
            )
        )


def _environment_python(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def smoke_installed_wheel(wheel: Path) -> None:
    """Install ``wheel`` and its dependencies into a clean environment and import it.

    The interpreter runs in isolated mode from a scratch directory, so neither
    ``PYTHONPATH`` nor a source checkout can stand in for the installed package.
    """
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    env = os.environ.copy()
    env["HNSWLIB_NO_NATIVE"] = "1"
    with tempfile.TemporaryDirectory(
        prefix="cytebase-wheel-smoke-", ignore_cleanup_errors=True
    ) as temp_dir:
        root = Path(temp_dir)
        environment = root / "environment"
        subprocess.run(
            ["uv", "venv", "--python", python_version, str(environment)],
            cwd=root,
            env=env,
            check=True,
        )
        python = _environment_python(environment)
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheel), "packaging"],
            cwd=root,
            env=env,
            check=True,
        )
        subprocess.run(
            [str(python), "-I", "-c", _SMOKE_CODE], cwd=root, env=env, check=True
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    validate_wheel_contents(wheel)
    smoke_installed_wheel(wheel)
    print(f"Wheel smoke passed: {wheel.name}")


if __name__ == "__main__":
    main()

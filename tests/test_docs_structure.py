import ast
import io
import json
import re
import tokenize
from pathlib import Path

import yaml

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_DOCS_SOURCE = _REPOSITORY_ROOT / "docs" / "source"
_API_SOURCE = _DOCS_SOURCE / "reference" / "api"
_PIPELINE = _REPOSITORY_ROOT / "cytebase" / "pipeline"
_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_CODE_FENCE = re.compile(r"(?ms)^```python\n(.*?)^```")
_AUTODOC_TARGET = re.compile(r"(?m)^\.\. auto\w+:: (\S+)")
_OLD_SDK_IMPORTS = re.compile(
    r"cytearc\.cytebase|from\s+cytearc\s+import\s+(?:\([^)]*|[^\n]*)\bcytebase\b"
)


def _project() -> dict:
    return yaml.safe_load((_DOCS_SOURCE / "myst.yml").read_text())["project"]


def _notebook_cells(path: Path) -> list[dict]:
    cells = json.loads(path.read_text())["cells"]
    for cell in cells:
        if not isinstance(cell["source"], str):
            cell["source"] = "".join(cell["source"])
    return cells


def _source_text(path: Path) -> str:
    if path.suffix != ".ipynb":
        return path.read_text()
    return "\n".join(cell["source"] for cell in _notebook_cells(path))


def _pages() -> list[Path]:
    return sorted(
        path
        for path in _DOCS_SOURCE.rglob("*")
        if path.suffix in {".md", ".ipynb"} and "_build" not in path.parts
    )


def _toc_files(entries: list[dict]) -> set[str]:
    files = {entry["file"] for entry in entries if "file" in entry}
    for entry in entries:
        files.update(_toc_files(entry.get("children", [])))
    return files


def _route_source(route: str) -> Path:
    """Return the source page that publishes ``route``, such as ``tutorials/cytebase``."""
    route = route.split("#", maxsplit=1)[0]
    if route.startswith("api/"):
        return _API_SOURCE / route.removeprefix("api/").replace(".html", ".md")
    stem = _DOCS_SOURCE / ("index" if route in {"", "./"} else route.strip("/"))
    stem = stem.with_name(stem.name.replace("-", "_"))
    candidates = [
        path
        for suffix in (".md", ".ipynb")
        if (path := stem.with_suffix(suffix)).is_file()
    ]
    assert len(candidates) == 1, (route, candidates)
    return candidates[0]


def _python_sources(path: Path) -> list[str]:
    """Return the code cells and Python fences that a page shows or runs."""
    if path.suffix == ".ipynb":
        cells = _notebook_cells(path)
        sources = [cell["source"] for cell in cells if cell["cell_type"] == "code"]
        markdown = "\n".join(
            cell["source"] for cell in cells if cell["cell_type"] == "markdown"
        )
    else:
        sources = []
        markdown = path.read_text()
    return sources + _CODE_FENCE.findall(markdown)


def _parser_names(path: Path, method: str) -> set[str]:
    """Return the string arguments of every ``method`` call in a module."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == method
        ):
            names.update(
                argument.value
                for argument in node.args
                if isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
            )
    return names


def test_llms_index_links_to_local_documentation() -> None:
    contents = (_DOCS_SOURCE / "llms.txt").read_text()
    targets = _MARKDOWN_LINK.findall(contents)

    assert targets
    for target in targets:
        assert "://" not in target
        source = _route_source(target)
        assert source.resolve().is_relative_to(_DOCS_SOURCE.resolve())
        assert source.is_file(), target


def test_navigation_publishes_every_page() -> None:
    project = _project()
    toctree = project["toc"]
    sections = {
        entry["title"]: entry["children"] for entry in toctree if "children" in entry
    }

    assert toctree[0] == {"file": "index.md"}
    assert list(sections)[0] == "Getting started"
    assert list(sections)[-2:] == ["Reference", "Developers"]
    assert {
        "installation.md",
        "tutorials/cytebase.ipynb",
    } <= _toc_files(sections["Getting started"])
    assert {
        "title": "API reference",
        "url": "/api/index.html",
        "open_in_same_tab": True,
    } in sections["Reference"]
    assert "llms.txt" in project["static_files"]
    assert "reference/api/**" in project["exclude"]

    published = _toc_files(toctree)
    for page in published:
        assert (_DOCS_SOURCE / page).is_file(), page
    for page in _pages():
        relative = page.relative_to(_DOCS_SOURCE)
        if relative.parts[:2] != ("reference", "api"):
            assert relative.as_posix() in published, relative


def test_relative_links_resolve_to_documentation_pages() -> None:
    for page in _pages():
        for target in _MARKDOWN_LINK.findall(_source_text(page)):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            if target.startswith("/"):
                source = _route_source(target.lstrip("/"))
            elif page.parent == _API_SOURCE:
                # Sphinx pages are served at /api/<page>.html, beside the MyST routes.
                source = _route_source(target.removeprefix("../"))
            else:
                path = target.split("#", maxsplit=1)[0]
                assert path.endswith((".md", ".ipynb")), (page, target)
                source = (page.parent / path).resolve()
            assert source.is_file(), (page, target)
            assert source.resolve().is_relative_to(_DOCS_SOURCE.resolve())


def test_documentation_imports_the_cytebase_package() -> None:
    # CyteArc 1.1 still ships an earlier copy of the SDK as cytearc.cytebase.
    for page in _pages():
        for source in _python_sources(page):
            assert not _OLD_SDK_IMPORTS.search(source), (page, source)
        for target in _AUTODOC_TARGET.findall(page.read_text()):
            assert target.startswith("cytebase."), (page, target)

    for name in ("cytebase.ipynb", "cytebase_covid19.ipynb"):
        cells = _notebook_cells(_DOCS_SOURCE / "tutorials" / name)
        code = "\n".join(
            cell["source"] for cell in cells if cell["cell_type"] == "code"
        )
        assert re.search(r"(?m)^import cytebase$", code), name


def test_documentation_links_cytearc_pages_on_the_cytearc_site() -> None:
    # CyteBase pages moved out of the CyteArc site, which keeps its analysis guides.
    sources = [*_pages(), _DOCS_SOURCE / "llms.txt", _DOCS_SOURCE / "myst.yml"]
    for source in sources:
        contents = _source_text(source)
        for retired in (
            "docs.nygen.io/CyteArc/tutorials/cytebase",
            "docs.nygen.io/CyteArc/api/cytebase",
        ):
            assert retired not in contents, (source, retired)
    composite = "https://docs.nygen.io/CyteArc/tutorials/composite-datasets"
    assert composite in (_DOCS_SOURCE / "index.md").read_text()
    assert composite in (_DOCS_SOURCE / "myst.yml").read_text()


def test_release_pages_name_the_latest_release() -> None:
    from cytebase._releases import LATEST

    for page in (_DOCS_SOURCE / "installation.md", _API_SOURCE / "cytebase.md"):
        assert f"Nygen/cytebase-{LATEST}" in page.read_text(), page


def test_installation_covers_plotting_and_import_check() -> None:
    contents = (_DOCS_SOURCE / "installation.md").read_text()

    assert "uv venv --python 3.13" in contents
    assert "python -m pip install cytebase" in contents
    assert 'uv pip install cytebase "cytearc[extra]"' in contents
    # Importing Catalog loads the modules that a bare import cytebase defers.
    assert "from cytebase import Catalog" in contents
    assert "uv pip install jupyterlab\njupyter lab" in contents
    assert "CYTEBASE_BUCKET" in contents
    assert "token=False" in contents


def test_build_pipeline_page_follows_the_pipeline_commands() -> None:
    contents = (_DOCS_SOURCE / "developers" / "build_pipeline.md").read_text()
    deploy = (_PIPELINE / "deploy.py").read_text()
    app = (_PIPELINE / "app.py").read_text()

    command = "uv run python -m cytebase.pipeline.deploy"
    assert command in contents
    assert command in ast.get_docstring(ast.parse(deploy))
    for name in ("cytearc-env", "cytebase-api", "CYTEBASE_API_TOKEN", "HF_TOKEN"):
        assert name in contents
        assert name in deploy or name in app
    options = {
        name
        for name in _parser_names(_PIPELINE / "deploy.py", "add_argument")
        if name.startswith("-")
    }
    assert options
    for option in options:
        assert f"`{option}`" in contents, option
    commands = _parser_names(_PIPELINE / "__main__.py", "add_parser")
    assert commands
    documented = set(re.findall(r"(?m)^\| `([a-z][a-z-]*)", contents))
    assert documented == commands


def test_notebook_comments_explain_each_step_on_their_own_lines() -> None:
    for notebook in sorted((_DOCS_SOURCE / "tutorials").glob("*.ipynb")):
        for cell in _notebook_cells(notebook):
            source = cell["source"]
            if cell["cell_type"] != "code" or not source.strip():
                continue
            lines = source.splitlines()
            assert lines[0].startswith("# "), (notebook.name, cell["id"])
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            for token in tokens:
                if token.type != tokenize.COMMENT:
                    continue
                row = token.start[0]
                assert token.line.strip().startswith("#"), (notebook.name, token.line)
                previous = lines[row - 2].strip() if row > 1 else ""
                assert row == 1 or not previous or previous.startswith("#"), (
                    notebook.name,
                    cell["id"],
                    token.line,
                )

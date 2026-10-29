# Documentation instructions

These instructions cover documentation sources, notebook execution, and site builds.

- Author executable pages as tracked `.ipynb` files in `docs/source/`. Each notebook is the page's sole source and contains its prose, code, outputs, and execution metadata.
- Keep prose guides and API references in Markdown.
- MyST builds guides and tutorials. Sphinx builds only `docs/source/reference/api/`.
- Import the SDK as `import cytebase` or `from cytebase import ...`, and use `cytebase.*` autodoc targets. Never use `cytearc.cytebase`: CyteArc 1.1 ships an earlier copy of the SDK under that name, so code using it silently runs different code.
- Link CyteArc pages with absolute `https://docs.nygen.io/CyteArc/...` URLs. Relative links must resolve to a page in `docs/source/`.
- `developers/build_pipeline.md` documents the operator-only `cytebase.pipeline`. Keep it in step with the module docstrings and command-line help in `cytebase/pipeline/`.

## Setup and rendering

Use Node.js 24 and install the Python tools:

```bash
uv sync --group docs --group docs-modal
make -C docs html
```

The site is written to ignored `docs/build/site/_build/html/`. Rendering does not execute code. Every executable notebook needs a completed execution timestamp, a matching code fingerprint, executed code cells, and no errors. Prose edits can reuse its outputs. Changed code requires re-execution and the updated notebook in the same change. For a lightweight source preview, use `make -C docs preview`; unexecuted pages display a warning that figures and results are unavailable. Preview builds still reject changed code and incomplete or failed executions.

Pages excluded by `project.exclude` in `docs/source/myst.yml` remain source-only and need no saved execution. Builds clear the generated site and API output so excluded pages leave no old routes. Package, dependency, and catalog release changes require judgment about which pages to refresh; there is no dependency fingerprint or cache invalidation service.

Pull requests, release checks, and GitHub Pages validate and render the notebooks from the checkout with `make -C docs html`. CI does not execute them. Missing, failed, or stale executions fail the build. GitHub Pages publishes from `master` at `https://docs.nygen.io/CyteBase/`. The workflow builds with `BASE_URL=/CyteBase` and uploads the generated site as the Pages artifact; the organization's Pages site serves it under `/CyteBase/` and owns the root `robots.txt`. Keep rendered site files outside Git.

## Execute affected pages on Modal

Select the environment explicitly:

```bash
make -C docs execute-docs-modal PAGES="cytebase cytebase_covid19" MODAL_ENVIRONMENT=your_environment
```

One invocation submits all selected source notebooks concurrently, one container per page. Each successful execution atomically replaces the same `.ipynb` file in `docs/source/` and records `metadata.executed_at` and `metadata.executed_code_sha256`. The latter identifies the executed code; do not edit this fingerprint by hand. Failed pages raise an error and leave their previous notebook intact. Rerun the failed pages directly.

The runner automatically records each code cell's UTC start time and elapsed wall time and displays them below its output. CPU time is not measured. Keep `%%time` out of notebook cells.

Do not start another invocation writing the same notebooks, or render while notebooks are being replaced. The container runs the checkout's `cytebase` source with the dependencies that `uv.lock` pins, including CyteArc. Notebook pages pin the catalog release they read, such as `Catalog(version="2610")`, and read public buckets anonymously; this runner injects no secrets. Catalog builds and release publication are separate operator actions requiring explicit authorization.

## Checks

```bash
uv run pytest -n 0 tests/test_docs_structure.py tests/test_docs_render.py \
    tests/test_docs_execution.py
make -C docs check-reference
```

The API check is a nitpicky, warnings-as-errors Sphinx build. Its inventory must document every `cytebase.__all__` export and `cytebase.display.CatalogResults` under their public names, and every public `Catalog`, `DatasetEntry`, `Release`, and `CatalogResults` member exactly once. Inspect the rendered figures and downloaded notebook after changing execution or presentation.

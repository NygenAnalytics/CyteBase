# Repository instructions

These instructions apply to the whole repository.

## Start here

- Edit the published SDK in `cytebase/`, the Modal build pipeline in `cytebase/pipeline/`, tests in
  `tests/`, documentation in `docs/`, and the agent skill in `skills/cytebase/`.
- Before analysing data with CyteBase, read `skills/cytebase/SKILL.md`. Analysis steps on an opened
  or mounted DataStore follow CyteArc's `cytearc-single-cell` skill. When a change alters a public
  API that a skill recipe uses, update the recipe in the same change.
- Read `docs/AGENTS.md` before executing or publishing documentation.

## CyteBase developer mental model

- `Catalog` downloads one verified DuckDB catalog per release bucket and answers searches locally.
  `DatasetEntry` describes a catalog row without opening its store. `Catalog.open_datastore` and
  `Catalog.mount_datastore` return CyteArc `DataStore` objects after checking the dataset's published
  record and build receipt against the opened arrays.
- Releases are public Hugging Face buckets named `Nygen/cytebase-YYMM` or `Nygen/cytebase-YYMM.N`,
  listed in `cytebase/_releases.py`. A published release never changes in place.
- The pipeline inspects CELLxGENE H5AD sources, converts them with CyteArc, verifies the stores
  against their sources, and publishes records and the catalog. Its outputs are persisted
  contracts: `dataset.json` records, build receipts, `cytearc_ingest.json`, the catalog schema, and
  the `.cytebase.json` mount receipt. Change their shapes only with an explicit compatibility
  decision; do not add silent migrations.

## CyteArc boundary

- The SDK depends on `cytearc>=1.1.0,<2` and must keep working across that range. CyteArc does
  not depend on CyteBase, and it opens CyteBase datasets by their `hf://` URIs. Import CyteArc
  through its public facades. `tests/test_cytearc_boundary.py` lists the few private CyteArc
  names the SDK uses, with the reason for each, and fails when CyteArc stops providing one. Prefer
  a public CyteArc API over a new entry.
- CyteArc 1.1 ships an earlier copy of this SDK as `cytearc.cytebase`; later CyteArc releases keep
  only their example-data downloads under that name. Never import `cytearc.cytebase` here.
- The pipeline is not published and may use CyteArc internals. It runs against the CyteArc version
  that `uv.lock` pins, and its build receipts record `cytearcVersion`. After upgrading CyteArc in
  the lock, run the complete suite, including the pipeline tests.
- CyteArc's own analysis features, such as composite stores, belong in CyteArc. CyteBase adds what
  needs the catalog: discovery, provenance, and choosing and assembling datasets across studies.

## Source and conventions

- Python 3.13 or newer is required. Use `uv` for every Python command and dependency change.
- Preserve unrelated working-tree changes. Trace callers and tests before changing a public
  function or a persisted record.
- Use built-in generics and `X | None`. Do not add `typing.List`, `typing.Optional`, or
  `from __future__ import annotations`.
- Pydantic model attributes use camel case.
- Do not add implicit compatibility branches, ad hoc schema versions, or silent migrations.
- Do not commit credentials, Modal secrets or tokens, private bucket names, or local endpoints.
- Avoid em dashes in public prose, prompts, docstrings, and comments.

## Environment and checks

```bash
uv sync
uv run pytest
uv run ruff check cytebase tests docs
uv run ruff format --check cytebase tests docs
uv run mypy cytebase
```

Run focused tests without pytest-xdist: `uv run pytest -n 0 tests/test_file.py::test_name`. After a
packaging change, build and check the wheel:

```bash
uv build
uv run --no-project python tests/smoke_wheel.py dist/*.whl
```

## Universal safety

- Never deploy or run the Modal pipeline, and never write to a CyteBase bucket. Deployment
  (`uv run python -m cytebase.pipeline.deploy`) and publication are user actions. Ask before any
  paid or long-running cloud job.
- Do not publish datasets, catalogs, or releases, or use write credentials, unless the user
  explicitly requests it.

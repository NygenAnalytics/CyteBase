# Open and mount

Open a CyteBase dataset read-only, mount it for analysis that saves results, reopen a mount, and
decide when to make a local copy of the counts.

## When to use

- Reading cell metadata, the authors' UMAP, or a few genes of one dataset: open read-only.
- Saving anything (cell selections, inserted columns, artifacts, pipeline runs, markers): mount.
- Returning to a mount in a later session, or planning many passes over the counts.

## Key concepts

- `catalog.open_datastore(cytebase_id, **datastore_options)` checks the catalog again, reads the
  published `dataset.json` record, requires it to be ready for its latest CELLxGENE version with an
  inspection and build receipt that agree, and opens the remote store with `zarr_mode="r"`,
  `min_features_per_cell=-1`, `default_assay="RNA"`, and `zarrProfile="cloud"`. It then checks the
  cell and gene counts and the count dtype against the receipt, and reads the record again to
  confirm nothing was republished during the open. It writes nothing, locally or remotely.
- `catalog.mount_datastore(cytebase_id, at, **datastore_options)` runs the same checks, creates a
  local writable store at `at` with copied cell and feature metadata whose counts resolve from the
  published store (its root `matrixSource` attribute), and then writes the receipt
  `<at>.cytebase.json` beside it. With an existing `at`, it reopens only when that receipt equals
  the current build's identity and the mount's `matrixSource` points at the same store.
- The receipt holds the build identity and no credentials: `cytebaseId`, `datasetId`,
  `processedVersionId`, `sourceSha256`, `zarrUri`, `verifiedAt`, `nObs`, `nVars`, `countsDtype`.
  `zarrUri` names the release bucket, so a mount belongs to one release.
- A mount resolves its source's artifacts read-only (the imported UMAP and the import cell
  selection) and writes new artifacts, columns, and pipeline runs locally. The published store is
  never modified, and other people can mount the same dataset independently.
- `datastore_options` pass through to `cytearc.DataStore`: `mem_budget`, `nthreads`, and other
  open options. `default_assay` defaults to `"RNA"` and `min_features_per_cell` to `-1`. The catalog
  manages `zarr_loc`, `storage_options`, and `zarr_mode`; credentials come from
  `Catalog(token=...)` and are supplied afresh on every open.
- Network and memory: an open fetches small metadata objects, which stay cached in memory for that
  store, and reads count chunks only when an operation needs them; there is no persistent local
  count cache. A request for one gene can fetch a larger chunk. Metadata tables and coordinates
  materialize only the requested columns, in memory proportional to the cells. On a mount every
  pass over counts (QC metrics, HVGs, normalization, markers, gene plots, pipelines) is a network
  read, while artifacts are local.
- Typical costs (from runs and the CyteArc docs; they vary with network and size): `Catalog()` and
  each query take seconds; a read-only open takes 10 to 30 s for up to about 45,000 cells; a new
  mount takes a few minutes for a few thousand cells; a pipeline on a mount of a few thousand cells
  takes about a minute; the four-study composite example (233,870 cells) took about 15 minutes per
  pipeline run.

## Recipes

### Open read-only and inspect

```python
import cytearc
import cytebase

cytearc.configure_output(level="WARNING", progress=False)
catalog = cytebase.Catalog(version="2610")
cytebase_id = "wilk_2020_single_cell_atlas_peripheral_sars_cov_2_infection_456e8b9b"

ds = catalog.open_datastore(cytebase_id, mem_budget="8G", nthreads=4)  # read-only, verified
print(ds)                                           # cells, assays, cell and feature columns
snap = ds.summary().to_dict()                       # JSON-safe and metadata only
print(snap["zarr_mode"], snap["default_assay"], snap["total_cells"], snap["pipeline_run_counts"])
print(ds.artifacts.list(complete_only=True))        # the imported embedding, if any
genes = ds.RNA.feats.to_pandas_dataframe(["ids", "names"])   # Ensembl IDs and gene symbols
meta = ds.cells.to_pandas_dataframe(["ids", "donor_id", "disease", "is_primary_data"], key="I")
print(meta.groupby("disease", observed=True)["donor_id"].nunique(), meta["is_primary_data"].mean())
```

Keep `ds` for every later read and plot; a new `open_datastore` call repeats the verification.
Read-only stores return existing artifacts but refuse to compute new ones (most producers raise
`PermissionError`); mount for that.

### Check the counts before QC

The CyteBase build took counts from the matrix that CELLxGENE declares as raw (`raw/X` or `X`;
otherwise a single valid counts layer), recorded as `countsLocation`, and checked 100 evenly spaced
cells for finite, nonnegative, integer values. Integer counts can still be corrected or prefiltered
by the authors, so run the "Check the matrix first" recipe of `cytearc-single-cell`
`references/quality-control.md` on `ds` before choosing QC bounds.

```python
inspection = catalog.dataset(cytebase_id).record()["inspection"]
print(inspection["countsLocation"], inspection["apiRawDataLocation"], inspection["countsSampleMax"])
author_qc = [c for c in ds.cells.columns if c.startswith(("nCount_", "nFeature_"))]
print(author_qc)    # submitter QC columns, for example nCount_SCT beside nCount_RNA
```

On a mount, the CyteArc skill's `scripts/inspect_store.py work/<name>.zarr` runs the same checks
and profiles every metadata column.

### Mount for writable analysis

Use a new local path. Mounting copies metadata and verifies the source.

```python
import json
from pathlib import Path

work = Path("work")
work.mkdir(exist_ok=True)
analysis = catalog.mount_datastore(cytebase_id, at=work / "wilk.zarr", mem_budget="8G")
# Writes work/wilk.zarr (copied metadata, future artifacts) and work/wilk.zarr.cytebase.json
print(analysis.zarr_mode, analysis.cells.N, int(analysis.cells.fetch_all("I").sum()))
print(cytebase.embeddings(analysis))        # the source's imported UMAP, resolved read-only
receipt = json.loads((work / "wilk.zarr.cytebase.json").read_text())
print(receipt["zarrUri"], receipt["processedVersionId"], receipt["verifiedAt"])
```

Continue with `cytearc-single-cell`: inspect, choose QC with removal audits, then
`analysis.pipeline.run(label=..., snapshot_columns=[...])`. Use one mount per independent
analysis; branches of one analysis share a mount.

### Reopen a mount

```python
# Through a catalog of the same release: checks the receipt against the current build
catalog = cytebase.Catalog(version="2610")
analysis = catalog.mount_datastore(cytebase_id, at=work / "wilk.zarr")

# Without the catalog: counts resolve from matrixSource, whose source fingerprints are checked
analysis = cytearc.DataStore(str(work / "wilk.zarr"), min_features_per_cell=-1)
```

Pass `min_features_per_cell=-1` to plain `cytearc.DataStore`: its default of `10` removes
low-feature cells from `I` on a writable open. Add `storage_options={"token": False}` to force
anonymous reads of the source. Saved runs reopen with `analysis.pipeline.open(label=...)`.

### Copy the counts locally for many passes

A mount pays a network read on every pass. Repacking copies the counts once into a self-contained
local store, including the source's imported artifacts and your runs; it needs disk for `counts`
and `countsT`.

```bash
python -m cytearc.tools.repack_zarr work/wilk.zarr work/wilk_local.zarr --mem-budget 4G
```

Open the copy with `cytearc.DataStore("work/wilk_local.zarr", min_features_per_cell=-1)`. It has
no `matrixSource` and no receipt, so copy the receipt fields into your provenance record first
(`releases-and-provenance.md`).

## Parameters that matter

| Parameter | Default | Change when |
|---|---|---|
| `at` (mount) | required | always a new local path; a URI raises `ValueError` |
| `mem_budget`, `nthreads` | `CYTEARC_MEM_BUDGET`, `CYTEARC_WORKERS`, else detected | shared hosts; remote reads use more concurrent buffers with more workers |
| `min_features_per_cell` | `-1` | read-only opens accept only `-1`; on a mount keep `-1` and filter through QC selections |
| `default_assay` | `"RNA"` | never; published stores have one `RNA` assay |
| `zarr_mode` | `"r"` (open), `"r+"` (mount) | never; another value raises `ValueError` |
| `storage_options`, `zarr_loc` | set by the catalog | never; passing them raises `TypeError` |
| `zarrProfile` | `"cloud"` on read-only opens | never on `open_datastore` (duplicate keyword `TypeError`) |
| `Catalog(token=)` | `None`: Hugging Face login if present | `False` for anonymous reads |

## Check before moving on

- `ds.zarr_mode` is `"r"` for exploration and `"r+"` for a mount; `print(ds)` shows the expected
  cells and the `RNA` assay.
- `ds.summary().to_dict()["pipeline_run_counts"]["total"]` is `0` on a published store; any runs
  on a mount are your own.
- For a mount, `<path>.cytebase.json` exists beside it and its `zarrUri` names the release you
  pinned.
- The counts check found raw integer counts, or you recorded why another policy applies.
- Before a long job, note the cell count and planned count passes; prefer a repacked copy for many
  passes.

## Pitfalls

- `open_datastore` with any `min_features_per_cell` other than `-1` raises `ValueError`, and with
  `zarr_mode="r+"` too. Mounting with `zarr_mode="r"` raises.
- A mount path that exists without its receipt raises `FileExistsError` ("Destination exists
  without a CyteBase mount receipt"); so does a receipt without a mount ("A CyteBase mount receipt
  already exists at this destination"). Choose a new path; copying a mount without its receipt makes
  it reopenable only through `cytearc.DataStore`.
- Reopening through a catalog of another release, or after the dataset was rebuilt, raises
  `ValueError` ("This mount refers to a different dataset build"). Reopen with
  `Catalog(version=<the mount's release>)`; if the build itself changed, mount into a new path and
  keep the old mount for the record.
- The source must stay at its recorded URI. A plain reopen raises when the source counts no longer
  match the mount's recorded fingerprints.
- A mount cannot be a source of `create_composite`; use stores from `open_datastore` (or a repacked
  local copy) as composite sources (`cross-dataset.md`).
- Mounting a mount raises; repack first if you need a mount of a mount.
- `open_datastore` may raise `RuntimeError` ("not ready for its registered version") for a
  dataset that `ready_only=False` listed, and `RuntimeError` ("changed while opening") during a
  republication; retry later or choose another dataset.
- Anonymous Hugging Face access is rate limited, and several opens in a row use many requests. On
  `429 Too Many Requests`, wait for the window or log in. Catalog and record downloads retry
  transient failures with backoff before raising.
- One `DataStore` per process and thread. Run parallel analyses in separate processes with separate
  mount paths.
- Metadata reads of a million-cell atlas take memory proportional to its cells; request only the
  columns you need, with `key="I"`.

## See also

- `cytearc-single-cell` `references/data-access.md` (DataStore basics) and
  `references/performance-and-export.md` (budgets, long-running steps, repacking, export).
- `embeddings.md`: plotting the authors' UMAP from an open or a mount.
- `releases-and-provenance.md`: receipts, release pinning, and records.

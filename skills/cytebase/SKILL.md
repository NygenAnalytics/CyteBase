---
name: cytebase
description: Find, compare, and open public single-cell RNA datasets from CyteBase, the versioned catalog of CELLxGENE Discover datasets published as cloud-hosted CyteArc DataStores. Covers catalog search, exact facet filters and SQL over the local DuckDB catalog, dataset entries and build records, read-only remote opens, writable local mounts with .cytebase.json receipts, imported UMAPs, release pinning and provenance, and choosing comparable datasets for joint reanalysis with cytearc.composite. Use when a task mentions CyteBase, the cytebase package or cytebase.Catalog, a CyteBase ID or release, or finding public CELLxGENE data to analyze or compare across studies with CyteArc. Analysis after opening (QC, clustering, markers, integration, donor-level tests, export) uses the cytearc-single-cell skill. Does not cover the operator-only cytebase.pipeline build.
license: BSD-3-Clause
compatibility: Requires Python 3.13+ and the cytebase package (pip install cytebase, which installs cytearc>=1.1.0,<2), plus network access to Hugging Face. Plotting through ds.plots needs cytearc[extra]. Public releases need no credentials.
metadata:
  version: "0.1"
---

# CyteBase datasets for CyteArc

CyteBase publishes public single-cell RNA datasets, currently converted from CELLxGENE Discover,
as CyteArc DataStores in versioned Hugging Face buckets, with a searchable catalog. This skill
encodes how to find datasets, judge whether they are comparable, open or mount them without
downloading counts, combine several for joint reanalysis, and record which release and build each
result came from.

Analysis of an opened store (QC, clustering, markers, integration, donor-level tests, export)
follows the CyteArc skill `cytearc-single-cell`:
<https://github.com/NygenAnalytics/CyteArc/tree/master/skills/cytearc-single-cell>. Read it before
computing anything on a store.

Read this file first, then open only the reference modules you need (index below). Paths are
relative to the skill directory. The maintained copy lives at
<https://github.com/NygenAnalytics/CyteBase/tree/master/skills/cytebase>. Examples use release
`2610`; IDs, counts, and labels are illustrations from it, not thresholds.

## Setup

- `pip install cytebase` installs the SDK and CyteArc (`cytearc>=1.1.0,<2`). Add
  `pip install "cytearc[extra]"` for `ds.plots` and AnnData export. Python 3.13 or newer.
- Import the package itself: `import cytebase` or `from cytebase import Catalog`. Code that uses
  `cytearc.cytebase` is legacy; do not write new code against it.
- Every catalog query and every count read needs network access to Hugging Face; there is no
  offline mode. Public releases need no credentials. `Catalog(token=None)` (the default) uses a
  Hugging Face login when one exists, `token=False` forces anonymous access. Anonymous access is
  rate limited (the CyteArc docs cite 500 requests per 5 minutes per IP address) and opening a store
  uses a share of that; `hf auth login` raises the limit. Never print or commit tokens or private
  bucket names.
- Set CyteArc resources before importing it, `CYTEARC_MEM_BUDGET=8G CYTEARC_WORKERS=8`, or pass
  `mem_budget=` and `nthreads=` to `open_datastore`, `mount_datastore`, and `create_composite`.
- Quiet, shareable output: `cytearc.configure_output(level="WARNING", progress=False)` and
  `logging.getLogger("huggingface_hub").setLevel(logging.ERROR)` (retry messages can contain
  request URLs).
- Headless figures: `MPLBACKEND=Agg`, plot with `show=False`, then `result.save(path)` and
  `result.close()`.
- Opening many sources, building a composite, or running a pipeline over remote counts can take
  many minutes. Run such steps as logged background scripts with bounded waits, as
  `cytearc-single-cell` `references/performance-and-export.md` ("Run long steps from an agent
  shell") describes.

## Mental model

- **Release**: one public bucket `Nygen/cytebase-<version>`, with version `YYMM` or `YYMM.N`.
  `cytebase.releases()` lists them newest first. Release `2610` (October 2026) holds 1,372 RNA
  datasets with primary cells, from 376 CELLxGENE collections, built from a CELLxGENE Discover
  snapshot of 2026-10-10.
- **Catalog** (`cytebase.Catalog`): a checksum-verified local DuckDB copy of one release's catalog,
  with tables `datasets`, `dataset_terms`, and `collections`. It holds no counts. Every query checks
  the published checksum again.
- **DatasetEntry** (`catalog.dataset(id)`): one catalog row (`entry.row`) plus the published build
  record (`entry.record()`). Metadata only; it never opens a store.
- **Read-only open** (`catalog.open_datastore(id)`): a remote `DataStore` with `zarr_mode="r"`,
  verified against the dataset's build receipt. Writes nothing anywhere.
- **Mount** (`catalog.mount_datastore(id, at=path)`): a local writable `DataStore` whose counts stay
  in the release bucket, plus a `<path>.cytebase.json` receipt that pins the source build.
- **Published store**: one `RNA` assay of counts (integer-like, from the matrix CELLxGENE declares
  as raw), every cell of the source H5AD including non-primary cells, the CELLxGENE and study cell
  columns, CyteArc QC columns (`RNA_nCounts`, `RNA_nFeatures`, `RNA_percentMito`,
  `RNA_percentRibo`), and the authors' UMAP as an imported embedding when the source had a valid
  `obsm["X_umap"]`. No pipeline runs.
- **Composite** (`cytearc.composite.create_composite`): a local writable store over selected cells of
  several read-only sources. Counts stay in the sources; new results are local.
- **Provenance**: the release version, each dataset's `entry.row` identity fields
  (`zarr_uri`, `dataset_id`, `processed_version_id`, `pipeline_version`, `processed_at`), the
  build record's source checksum, a mount's receipt, and a composite's source bindings.

## Golden rules

1. **Pin the release.** Use `cytebase.Catalog(version="2610")`. A bare `Catalog()` follows the
   `CYTEBASE_BUCKET` environment variable when it is set, and otherwise whichever release is newest.
   Record the version with every result.
2. **Take IDs and labels from row dictionaries.** Printed `CatalogResults` tables escape Markdown
   characters (`_` shows as `&#95;`, `'` as `&#39;`) and shorten long cells. Use
   `row["cytebase_id"]` and `row["label"]`; never retype an ID from a table.
3. **Exact labels for filters.** `search` matches substrings of every word, so `T` or `B` matches
   nearly every dataset. `find_datasets` matches exact labels only, with no ontology descendants.
   Get labels from `catalog.list_terms(facet)`.
4. **Read-only first.** Use `open_datastore` to look. Mount only to save results; build a composite
   to analyze several datasets together. Each open re-verifies the build over the network, so keep
   the returned `ds` and reuse it.
5. **One mount per analysis and build.** Mount into a new local path, keep `<path>.cytebase.json`
   beside it, and reopen through a catalog of the same release. A rebuilt dataset or a newer release
   needs a new mount path.
6. **Every count pass is a network read.** Gene panels, QC, normalization, markers, and pipelines
   on opens, mounts, and composites all stream remote counts. Plan the passes; repack a single
   mount locally before many of them.
7. **Published annotations are author labels.** `cell_type`, `author_cell_type`, and study label
   columns came from the submitters. Hold them out when they will judge your result
   (`cytearc-single-cell` golden rule 14).
8. **Primary cells only when pooling.** Stores keep every source cell. Select `is_primary_data`
   before combining datasets, or the same cell can be counted twice.
9. **Donors are the unit.** Count donors per condition in each dataset before any comparison.
   Datasets of one collection often share donors (check the overlap); equal donor IDs in different
   collections do not prove the same person.
10. **Cite the source.** Keep `entry.citation` and the DOI of the original study, and credit
    CELLxGENE Discover, with every figure and table.

## Decision flow

| Goal | Route | Module |
|---|---|---|
| Find candidate datasets | `search` words, then `list_terms` and `find_datasets`, or SQL through `query` | `catalog-search.md` |
| Facts about one dataset: citation, size, labels, counts source | `catalog.dataset(id)`: `describe()`, `row`, `record()`; opens no store | `catalog-search.md` |
| Look at metadata, the published UMAP, a few genes | `catalog.open_datastore(id)` | `open-and-mount.md`, `embeddings.md` |
| Save anything: selections, columns, pipeline runs, markers | `catalog.mount_datastore(id, at=new_path)`, then the CyteArc skill | `open-and-mount.md` |
| Many passes over the counts of one dataset | mount, then repack into a local store | `open-and-mount.md` |
| Compare studies without pooling counts | donor-level summaries per dataset from metadata | `cross-dataset.md` |
| Joint reanalysis of several datasets | shortlist comparable datasets, open each read-only, `create_composite` | `cross-dataset.md` |
| Reproduce, reopen, or report where a result came from | pinned release, entry fields, receipts, composite bindings | `releases-and-provenance.md` |

## Quick start

Find a dataset, read its record, open it read-only, look at donors, plot the authors' UMAP, and
save provenance. Nothing is written to the remote store.

```python
import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; select the backend before importing cytearc
import cytearc
import cytebase

cytearc.configure_output(level="WARNING", progress=False)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
out = Path("cytebase_out")
out.mkdir(exist_ok=True)

release = next(r for r in cytebase.releases() if r.version == "2610")  # r.latest marks the default
catalog = cytebase.Catalog(version=release.version)

hits = catalog.search("wilk sars cov 2")          # every word, case-insensitive
print(hits.to_markdown(columns=["cytebase_id", "title", "cell_count"], max_cell_chars=40))
entry = catalog.dataset(hits[0]["cytebase_id"])  # the ID from the row, not from the table
print(entry.describe())                          # Markdown summary; opens no store

ds = catalog.open_datastore(entry.id)            # read-only; counts stay remote
print(ds)
umap = cytebase.embedding(ds, "X_umap")          # the authors' UMAP, imported with the data
meta = ds.cells.to_pandas_dataframe(["ids", "cell_type", "donor_id", "disease"], key="I").set_index("ids")
print(meta.groupby("disease")["donor_id"].nunique())   # donors, not cells, per condition

fig = ds.plots.embedding(layout=umap, color_by="cell_type", show=False)
fig.save(out / "umap_cell_type.png", dpi=150)
fig.close()

provenance = {
    "release": release.version, "bucket": release.bucket, "cytebaseId": entry.id,
    "zarrUri": entry.row["zarr_uri"], "cellxgeneVersionId": entry.row["processed_version_id"],
    "pipelineVersion": entry.row["pipeline_version"], "citation": entry.citation,
}
(out / "cytebase_provenance.json").write_text(json.dumps(provenance, indent=2))
```

Next: to save results, mount (`references/open-and-mount.md`) and continue with
`cytearc-single-cell`; to combine studies, read `references/cross-dataset.md`.

## Record what you used

Keep these beside the analysis so another agent or a person can reproduce it:

- `cytebase_provenance.json`: the release version and bucket, and for each dataset the fields of
  "Record dataset provenance" in `references/releases-and-provenance.md`.
- For a mount, its `<path>.cytebase.json` receipt (copy it into the handoff); for a composite, the
  source names, CyteBase IDs, and the row selection rule.
- The selection rationale: search terms, facet filters or SQL, and why each dataset was kept or
  dropped.
- The CyteArc handoff of `cytearc-single-cell` (`handoff.json`, run report, lineage).

## Reference modules

| Module | Read when |
|---|---|
| `references/catalog-search.md` | searching, facet labels, SQL over `datasets`, `dataset_terms`, and `collections`, result tables, entries and build records |
| `references/open-and-mount.md` | read-only opens, mounts and receipts, reopening, rejected options, network, memory, and repacking |
| `references/embeddings.md` | which embeddings exist, coordinates by cell ID, plotting the authors' UMAP |
| `references/releases-and-provenance.md` | releases and buckets, pinning, what can change, provenance records, receipts, composite bindings, citation |
| `references/cross-dataset.md` | choosing comparable datasets, primary cells and donors, metadata-only comparisons, composites and their analysis |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ValueError: Supply bucket= or version=, not both` | both arguments given | pass one |
| `ValueError: CyteBase version must be YYMM or YYMM.N ...` | malformed version | a `version` string from `cytebase.releases()` |
| `KeyError: No catalog dataset is registered as ...` (`dataset`), `KeyError: No dataset is registered as ...` (open, mount) | ID retyped or copied from a printed table | `row["cytebase_id"]` from the results |
| `ValueError: CyteBase IDs use 1 to 80 lowercase letters, digits, or underscores` | an ID with HTML entities such as `&#95;` from a printed table | `row["cytebase_id"]` from the results |
| `HfHubHTTPError: 401 Unauthorized` from `Catalog(version=...)` | no such release, or a private bucket without access | a version from `cytebase.releases()`; credentials for private buckets |
| `find_datasets` returns nothing | label not exact, a compound label (`A \|\| B`), facets combined with AND, or `organ` (no terms in `2610`) | labels from `list_terms(facet)`; `tissue` instead of `organ` |
| `search` returns nearly everything | short words match as substrings | longer words, or exact facets |
| `ValueError: Read-only access requires min_features_per_cell=-1 ...` | a cell filter on a read-only open | leave it unset; filter with QC selections on a mount |
| `ValueError: This CyteBase access requires zarr_mode='r'` (or `'r+'`) | `zarr_mode` passed to `open_datastore` or `mount_datastore` | leave it unset |
| `TypeError: storage_options is resolved by Catalog ...` (or `zarr_loc`) | the catalog supplies these | set `token=` or `bucket=` on `Catalog` |
| `TypeError: ... multiple values for keyword argument 'zarrProfile'` | `open_datastore` already sets `zarrProfile="cloud"` | leave it unset |
| `RuntimeError: Dataset ... is not ready for its registered version` | no verified store for the latest CELLxGENE version | another dataset, or keep `ready_only=True` |
| `RuntimeError: The published dataset changed while opening it ...` | republished during the open | retry, then record the new build |
| `ValueError: ... provenance does not match ...` or `... differs from the committed build receipt` | inconsistent publication | do not use the dataset; report it to the publisher |
| `FileExistsError: Destination exists without a CyteBase mount receipt ...` | path in use, or a mount copied without its receipt | a new path, or open the copy with `cytearc.DataStore` |
| `ValueError: This mount refers to a different dataset build ...` | build changed, or a catalog of another release | `Catalog(version=<mount release>)`; otherwise a new mount |
| `KeyError: Embedding 'X_pca' was not imported ...` | only `X_umap` is imported | `cytebase.embeddings(ds)`; compute new embeddings on a mount |
| `PermissionError` from a CyteArc producer | the store was opened read-only | mount the dataset |
| `429 Too Many Requests` | anonymous rate limit | wait for the window, or `hf auth login` |
| `ValueError: Mounted and composite sources are not supported` | a mount or composite passed to `create_composite` | pass stores from `catalog.open_datastore` |
| `ValueError: Composite source identity changed: <name>` | a source build changed after creation | rebuild the composite from current sources |

## Documentation and related skills

- `cytearc-single-cell`: everything after the open, including QC removal audits, pipelines,
  annotation, Harmony safety, donor-level tests, plotting, and export.
- CyteBase documentation: <https://docs.nygen.io/CyteBase/>: installation, the "Explore CyteBase"
  tutorial (`tutorials/cytebase/`), the COVID-19 blood case study (`tutorials/cytebase-covid19/`),
  and the API reference (`api/cytebase.html`).
- CyteArc documentation: <https://docs.nygen.io/CyteArc/>: joint reanalysis of CyteBase datasets
  with composites (`tutorials/composite-datasets`), remote stores and mounts, batch correction,
  and condition comparisons.
- `cytebase.pipeline` builds and publishes releases. It is operator-only, runs on Modal from a
  checkout, and is not part of the installed package; data users never need it.

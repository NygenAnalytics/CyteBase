---
description: Search a catalog of public single-cell datasets and open them as cloud-hosted CyteArc DataStores without downloading complete datasets.
---

# CyteBase

**A searchable catalog of public single-cell datasets, stored as cloud-hosted CyteArc
DataStores.**

Search by study, tissue, disease, or organism, then open a dataset from a local notebook or a
cloud Python session. Explore its published cell annotations, imported embeddings, and gene
expression without downloading an H5AD or a complete store. Public access needs no credentials.

[Install CyteBase](installation.md) · [Explore the catalog](tutorials/cytebase.ipynb) ·
[API reference](/api/index.html)

## What the catalog contains

The datasets come from CZ CELLxGENE Discover. Each public release is a separate, read-only
Hugging Face bucket named by year and month. The October 2026 release (`2610`, in
`Nygen/cytebase-2610`) was built from a CELLxGENE Discover snapshot taken on 2026-10-10 and
contains primary RNA datasets from 376 registration-ready collections, converted to CyteArc
stores. `cytebase.releases()` lists every release with its bucket, notes, and changelog.

Each catalog entry records the dataset's title, citation, CELLxGENE links, size, and ontology
labels for its tissues, diseases, cell types, assays, and organisms. The stores hold the RNA
counts with the published cell annotations. When a dataset provides a usable UMAP
(`obsm/X_umap`), the build imports it, so it can be plotted without recomputing an embedding.
Cite the original study and CELLxGENE Discover when you use these data.

## A first example

```python
import cytebase

# Connect to the latest public release; no credentials are needed.
catalog = cytebase.Catalog()

# Search IDs, titles, citations, authors, and ontology labels.
matches = catalog.search("kidney")
print(matches)

# Open one of the matching datasets for read-only exploration.
dataset_id = matches[0]["cytebase_id"]
ds = catalog.open_datastore(dataset_id)

# Plot the imported UMAP; plotting needs CyteArc's extra dependencies.
umap_ref = cytebase.embedding(ds, "X_umap")
ds.plots.embedding(layout=umap_ref, color_by="cell_type")

# Create a writable local store for your own analysis, keeping counts remote.
analysis = catalog.mount_datastore(dataset_id, at="kidney_analysis.zarr")
```

## How it works

- **A local, verified catalog.** `Catalog()` keeps a small DuckDB copy of the catalog on your
  machine and checks it against the published SHA-256 checksum before each query. Searching
  never reads count data.
- **Remote DataStores.** `open_datastore` validates the published build and returns a read-only
  CyteArc `DataStore`. CyteArc reads metadata and count blocks over the network as needed, and
  computation runs where your Python session runs.
- **Writable mounts.** `mount_datastore` creates a local CyteArc store for new analysis results
  while the counts stay in the bucket. Use it with CyteArc's analysis pipeline.
- **Reproducible releases.** Pin a release with `Catalog(version="2610")` to reproduce
  discovery results; newer releases may return different matches.

## Next steps

- {ref}`Installation <installation>` covers the Python requirements, plotting dependencies,
  releases, credentials, and network access.
- [](tutorials/cytebase.ipynb) searches the catalog, reads annotations, plots the imported UMAP
  and gene expression, and queries the catalog with SQL.
- [](analyze_with_cytearc.md) mounts a small dataset and runs CyteArc's RNA pipeline on it.
- [](tutorials/cytebase_covid19.ipynb) compares COVID-19 and healthy blood with donor-level
  summaries.
- [Joint reanalysis of CyteBase datasets](https://docs.nygen.io/CyteArc/tutorials/composite-datasets)
  in the CyteArc documentation combines several CyteBase datasets into one analysis.
- The [CyteArc documentation](https://docs.nygen.io/CyteArc/) describes the analyses you can
  run on an opened or mounted store.
- The [API reference](/api/cytebase.html) lists every public function and class.
- [](developers/build_pipeline.md) describes how operators build and publish releases.

Report problems in the [issue tracker](https://github.com/NygenAnalytics/CyteBase/issues).
The [documentation index for LLMs](https://docs.nygen.io/CyteBase/llms.txt) lists guides and
API references for assistants that read this site.

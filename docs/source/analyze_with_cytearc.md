---
description: Find a small CyteBase dataset, mount it as a writable CyteArc store with remote counts, and run CyteArc's RNA pipeline on it.
---
(analyze_with_cytearc)=

# Analyze a dataset with CyteArc

CyteBase finds and opens published datasets; [CyteArc](https://docs.nygen.io/CyteArc/) analyzes
them. This quick example mounts a small dataset as a local, writable CyteArc store whose counts
stay in the bucket, runs CyteArc's RNA pipeline on it, and plots the result. Plotting needs
CyteArc's plotting dependencies, described in {ref}`Plotting <installation_plotting>`. The whole
example takes a few minutes for the 1,790-cell dataset it selects.

## Choose a dataset

```python
import cytearc
import cytebase

# Keep routine pipeline progress out of the output.
cytearc.configure_output(level="WARNING", progress=False)

# Pin the October 2026 release and read it anonymously.
catalog = cytebase.Catalog(version="2610", token=False)

# List the smallest ready human datasets with at least 1,500 cells.
small = catalog.query(
    "SELECT cytebase_id, title, cell_count FROM datasets "
    "WHERE status = 'ready' AND processed_version_id = latest_version_id "
    "AND list_has_any(organism_labels, ['Homo sapiens']) AND cell_count >= 1500 "
    "ORDER BY cell_count, cytebase_id LIMIT 5"
)
dataset_id = small[0]["cytebase_id"]
```

In release `2610`, the first row is `mcglade_2021_scrna_data_human_fallopian_tube_30f5e171`, a
fallopian tube dataset with 1,790 cells. [](tutorials/cytebase.ipynb) shows the other ways to
search the catalog.

## Mount the dataset and run the pipeline

```python
# Create a writable local store; its counts stay in the bucket.
analysis = catalog.mount_datastore(dataset_id, at="quickstart.zarr")

# Run CyteArc's RNA pipeline; every result is saved in quickstart.zarr.
run = analysis.pipeline.run(label="baseline")

# Color the computed UMAP by the selected clustering.
analysis.plots.embedding(run=run, color_by="clusters")
```

The pipeline filters cells, selects highly variable genes, and computes PCA, a neighbour graph, a
UMAP, Leiden and Paris clusterings, doublet scores, and marker genes. It reads count blocks from
the bucket as it needs them, so it runs wherever your Python session runs.

## Read the results

```python
# Show the three strongest markers of each cluster.
markers = analysis.markers.load(marker=run["markers"])
markers.groupby("group_id", sort=False).head(3)[["group_id", "feature_name"]]
```

The mount keeps your results. Reopen it in a later session with
`catalog.mount_datastore(dataset_id, at="quickstart.zarr")`, which checks it against the same
published build, or with `cytearc.DataStore("quickstart.zarr", min_features_per_cell=-1)`.

## Next steps

- CyteArc's [scRNA-seq tutorial](https://docs.nygen.io/CyteArc/tutorials/scrna-seq) explains
  each pipeline step and how to choose its settings.
- [Joint reanalysis in CyteArc](https://docs.nygen.io/CyteArc/tutorials/composite-datasets)
  combines several CyteBase datasets in one analysis without copying their counts.
- [](tutorials/cytebase_covid19.ipynb) compares donors across conditions using published
  annotations.

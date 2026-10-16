# Embeddings

Find the embeddings a CyteBase dataset carries, read their coordinates by cell ID, and plot the
authors' UMAP without recomputing it.

## When to use

- Plotting the published UMAP colored by metadata or genes.
- Reading coordinates for a custom figure or a table.
- Checking which source embeddings exist before deciding to compute your own.

## Key concepts

- The build imports one embedding: the source `obsm["X_umap"]`, when it is a dense, finite,
  two-dimensional array with one row per cell. Other source keys are not imported.
  `entry.source_embeddings()` lists every source `obsm` key (`X_pca`, `X_scVI`, `X_harmony`, ...),
  imported or not.
- An imported embedding is an `embedding` artifact of the `RNA` assay (operation `import_dimreduc`,
  parameter `dimreduc_key`). Its rows follow the artifact's frozen cell selection, not the live `I`.
- `cytebase.embeddings(ds, *, assay="RNA")` maps each imported key to its `ArtifactRef`.
  `cytebase.embedding(ds, key="X_umap", *, assay="RNA")` returns one ref; it raises `KeyError`,
  naming the available keys, when the key was not imported, and `ValueError` when it was imported
  more than once.
- `cytebase.embedding_coordinates(ds, ref)` returns a DataFrame indexed by cell ID (index name
  `ids`) with columns such as `umap_1` and `umap_2`.
- The helpers read artifact provenance only, so they work on any CyteArc DataStore: read-only
  opens, mounts (which resolve the source's imported UMAP read-only), and local copies. The CyteArc
  call `ds.artifacts.find("embedding", imported="X_umap", from_assay="RNA")` finds the same ref.
- Embeddings you compute (a pipeline run's `run["umap"]`) are not imports and do not appear in
  `cytebase.embeddings`. A composite carries no imported embeddings, so
  `cytebase.embeddings(joint)` is `{}`; a joint analysis computes its own layout.
- The authors' UMAP was computed on their cells, genes, and often their integration. It shows their
  analysis; it is not evidence for clusters or integration quality in yours.

## Recipes

### List what exists

```python
import cytearc
import cytebase

cytearc.configure_output(level="WARNING", progress=False)
catalog = cytebase.Catalog(version="2610")
entry = catalog.dataset("wilk_2020_single_cell_atlas_peripheral_sars_cov_2_infection_456e8b9b")
print(entry.source_embeddings())          # source obsm keys, for example ['X_pca', 'X_umap']
ds = catalog.open_datastore(entry.id)
refs = cytebase.embeddings(ds)            # imported keys only: {'X_umap': ArtifactRef(...)}
print(refs)
umap = cytebase.embedding(ds, "X_umap")   # KeyError if the source had no usable X_umap
```

### Read coordinates by cell ID

```python
coords = cytebase.embedding_coordinates(ds, umap)        # index "ids"; columns umap_1, umap_2
meta = ds.cells.to_pandas_dataframe(["ids", "cell_type", "donor_id"], key="I").set_index("ids")
frame = coords.join(meta, how="inner")                   # join on cell IDs, never on row order
print(frame.shape, frame.isna().sum().to_dict())
```

### Plot the published UMAP

Run headless with `MPLBACKEND=Agg` and `show=False`. Metadata colors read cell columns; each gene
reads count blocks over the network, so keep gene panels small.

```python
from cytearc.plotting import NormalizationSpec

fig = ds.plots.embedding(layout=umap, color_by="cell_type", legend_loc="right", show=False)
fig.save("umap_cell_type.png", dpi=150)
fig.close()
genes = ds.plots.embedding(
    layout=umap, color_by=["MS4A1", "CD14"], normalization=NormalizationSpec(transform="log1p"),
    sort_values=True, n_columns=2, show=False,
)
genes.save("umap_genes.png", dpi=150)
genes.close()
```

`facet_by="disease"` splits panels by a column, `groups=[...]` restricts the shown groups, and
`legend_loc="none"` keeps a large atlas readable. Every `ds.plots` method is described in
`cytearc-single-cell` `references/plotting.md`.

### Use the published UMAP on a mount

The same calls work on a mount, and your new columns can color the published layout:

```python
refs = cytebase.embeddings(analysis)          # the source's X_umap, resolved read-only
fig = analysis.plots.embedding(layout=refs["X_umap"], color_by="my_column", show=False)
```

After a pipeline run on the mount, plot your own layout with `analysis.plots.embedding(run=run,
color_by="clusters", show=False)` and compare it with the published one; they need not agree.

## Parameters that matter

| Parameter | Default | Change when |
|---|---|---|
| `cytebase.embedding(key=)` | `"X_umap"` | another imported key; current builds import only `X_umap` |
| `assay=` | `"RNA"` | never for CyteBase stores |
| `ds.plots.embedding(layout=)` | `None` | pass the imported ref to draw the published layout |
| `normalization=` | assay default | `NormalizationSpec(transform="log1p")` for gene colors |
| `legend_loc=` | `"auto"` | `"right"` or `"none"` for many labels |

## Check before moving on

- `cytebase.embeddings(ds)` contains the key you plot; `entry.source_embeddings()` alone is not
  enough.
- The coordinate frame joined to metadata by `ids` has no unexpected missing values.
- Figures were saved and closed; every gene panel was a deliberate network read.

## Pitfalls

- `X_pca`, `X_scVI`, or `X_harmony` in `source_embeddings()` are not in the store;
  `cytebase.embedding(ds, "X_pca")` raises `KeyError: Embedding 'X_pca' was not imported for assay
  'RNA'; available: X_umap`.
- Some sources have no usable `X_umap`; then `cytebase.embeddings(ds)` is `{}` and only a computed
  embedding (on a mount) can be plotted.
- `embedding_coordinates` requires an embedding `ArtifactRef` (`TypeError` otherwise). Its rows are
  the embedding's frozen cells, which can include cells outside your current selection: always join
  by cell ID.
- When a key is imported twice (for example a mount that imported its own copy), both helpers raise
  `ValueError`; choose an explicit ref from `ds.artifacts.list(kind="embedding", complete_only=True)`.
- Do not choose clusters, QC thresholds, or integration settings by eye on the published UMAP, and
  do not color it with held-out author labels when those labels will judge your result.

## See also

- `open-and-mount.md`: opening or mounting the dataset first.
- `cytearc-single-cell` `references/plotting.md` and `references/clustering-and-embedding.md`.

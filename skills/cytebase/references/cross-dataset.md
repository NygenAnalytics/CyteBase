# Cross-dataset investigation

Choose comparable CyteBase datasets across studies, compare them without pooling counts, or pool
selected cells into a composite for joint reanalysis while the counts stay remote.

## When to use

- A question spans studies: does a population, state, or expression difference replicate across
  cohorts, tissues, or technologies?
- Building a shortlist of comparable datasets before opening any of them.
- A joint analysis needs one feature space, one graph, shared clusters, or pooled markers across
  datasets.

## Key concepts

- **Two routes.**
  1. *Analyze each dataset, then compare*: summarize per donor within each dataset (from metadata
     alone, or from a mount per dataset), then compare the direction and size of effects across
     studies. Study differences stay out of every estimate, and no shared feature space is needed.
     Prefer this route for replication questions.
  2. *Joint reanalysis*: `cytearc.composite.create_composite` pools selected cells of several
     read-only sources into one local writable store, and one CyteArc pipeline runs over all of
     them. Needed for a shared embedding, shared clusters, label transfer across studies, or pooled
     markers.
- **Comparability.** Check every axis below before pooling; record what differs.

| Axis | Where to look | Why it matters |
|---|---|---|
| organism | `organism_labels` | feature IDs (Ensembl) differ between species; an intersection is empty |
| measurement | `assay_labels`, `suspension_types` | 3' and 5' chemistries, plate-based full-length methods, cells and nuclei, and spatial assays (`na`) detect genes differently |
| tissue and sampling | `tissue_labels`, study columns such as `tissue_type` | blood, PBMC fractions, biopsies, and organoids are different populations |
| conditions and controls | `disease_labels` (including compound labels), then donors per group after opening | a study with cases only cannot separate disease from study |
| duplicated cells | `primary_cell_count` against `cell_count`; per-cell `is_primary_data` | republished cells counted twice |
| studies and donors | `collection_id`, `donor_id` | datasets of one collection can share donors |
| counts | `record()["inspection"]["countsLocation"]`, submitter QC columns | corrected or prefiltered matrices distort QC and pooled models |
| annotations | `cell_type` and `cell_type_ontology_term_id`; author columns | ontology depth and author vocabularies differ between studies |
| genes | `n_genes`, feature `ids` | the shared feature space shrinks with every added study |

- **Primary cells.** CELLxGENE marks the canonical copy of each cell with `is_primary_data == True`;
  copies reused in other datasets carry `False`. CyteBase stores keep every source cell (106
  datasets in `2610` hold non-primary cells), so select primary cells before pooling.
- **Studies and donors.** A CELLxGENE collection often splits one study into sibling datasets that
  share donors: two cell-type subsets of one `2610` collection shared 68 of their 72 and 71 donor
  IDs. A collection can also republish independent studies: the Jin 2021 collection holds separate
  Arunachalam and Schulte-Schrepping cohorts. Donor IDs are strings chosen by each submitter, so
  check donor overlap between datasets of one collection, then decide and record whether donors
  are keyed by collection or by dataset. Equal donor strings in different collections do not prove
  the same person.
- **Composites** (`create_composite(sources, *, at, features, assay="RNA", rows=None,
  mem_budget=None, nthreads=None)`):
  - `sources` maps a name to an open `DataStore` that owns its counts: use stores from
    `catalog.open_datastore` (or local stores); mounts and composites are refused. Names become the
    values of the `dataset` column and the prefix of composite cell IDs (`<name>__<source id>`), so
    they must not contain `__`.
  - `features` is required: `"intersection"` keeps feature IDs present in every source; `"union"`
    keeps all and fills genes a source lacks with zeros, although absence is not zero expression.
  - `rows` gives, per source, positions in its full cell table (`fetch_all` order). Without
    `rows`, every stored cell is included, inactive and non-primary ones too.
  - The result is a writable local store: source cell columns with an `orig_` prefix, a `dataset`
    column, `RNA_I`, fresh QC columns, `I` all true, the aligned feature table, and no artifacts,
    embeddings, or runs from the sources. Its row order is a deterministic shuffle: chunk-sized
    blocks of different sources interleave and cells are permuted within blocks.
  - Creation scans the selected counts once and leaves them in the sources. Every later count pass
    reads the sources over the network, through a temporary cache of up to
    `CYTEARC_SOURCE_CACHE_BYTES` per open composite (2 GiB of `TMPDIR` when unset; `0` turns it
    off). The root attribute `composite` records each source's location and fingerprints, and a
    reopen refuses changed sources.
  - A composite cannot be mounted, repacked, or used as a composite source. `SubsetZarr` or
    `DataStoreMerge` can write an ordinary store with copied counts from it.
- Scale from the CyteArc composite tutorial (four COVID-19 blood studies, 233,870 cells,
  `mem_budget="6G"`, `nthreads=4`): opening the sources took about 1.5 minutes, creating the
  composite about 3.5 minutes, and each pipeline run about 15 minutes.

## Recipes

### Shortlist comparable datasets

```python
import cytearc
import cytebase

cytearc.configure_output(level="WARNING", progress=False)
catalog = cytebase.Catalog(version="2610")
READY = "status = 'ready' AND processed_version_id = latest_version_id AND zarr_uri IS NOT NULL"
candidates = catalog.query(
    f"""
    SELECT cytebase_id, collection_id, first_author, year, cell_count, primary_cell_count,
           n_genes, assay_labels, suspension_types, disease_labels
    FROM datasets
    WHERE {READY}
      AND list_has_any(organism_labels, ?)   -- one organism, so feature IDs can match
      AND list_has_any(tissue_labels, ?)
      AND list_has_all(disease_labels, ?)    -- cases and controls within each study
      AND list_has_any(suspension_types, ?)  -- dissociated cells
    ORDER BY cell_count DESC
    """,
    parameters=[["Homo sapiens"], ["blood"], ["COVID-19", "normal"], ["cell"]],
)
print(candidates.to_markdown(
    columns=["cytebase_id", "first_author", "year", "primary_cell_count", "assay_labels"],
    max_rows=None, max_cell_chars=40,
))
```

In `2610` this returns 13 datasets. Record the query and why each dataset was kept or dropped.

### Check build records and studies before opening

```python
import pandas as pd

review = []
for row in candidates:
    inspection = catalog.dataset(row["cytebase_id"]).record()["inspection"]
    review.append({
        "cytebase_id": row["cytebase_id"], "collection_id": row["collection_id"],
        "assays": ", ".join(row["assay_labels"]), "n_genes": row["n_genes"],
        "primary_fraction": round(row["primary_cell_count"] / row["cell_count"], 3),
        "counts_from": inspection["countsLocation"],
        "integer_like": inspection["countsIntegerLike"],
    })
review = pd.DataFrame(review)
print(review.groupby("collection_id")["cytebase_id"].count().loc[lambda n: n > 1])  # siblings
print(review.drop(columns="collection_id").to_string(max_colwidth=40))
```

Each `record()` call is one small download. Datasets that share a `collection_id` need the donor
overlap check below before they count as independent studies.

### Open the sources and audit the design

```python
import itertools

import numpy as np

dataset_ids = {           # names become `dataset` values and cell ID prefixes; no "__"
    "blood_wilk": "wilk_2020_single_cell_atlas_peripheral_sars_cov_2_infection_456e8b9b",
    "blood_lee": "lee_2020_immunophenotyping_covid_19_development_severe_covid_19_de2c780c",
    "blood_arunachalam": "jin_2021_individual_single_cell_rna_seq_pbmc_data_arunachalam_et_al_59b69042",
    "blood_schulte_schrepping": "jin_2021_individual_single_cell_rna_seq_data_schulte_schrepping_et_al_5e717147",
}
sources = {name: catalog.open_datastore(cid, mem_budget="6G", nthreads=4)
           for name, cid in dataset_ids.items()}
design = pd.concat(
    [ds.cells.to_pandas_dataframe(["donor_id", "disease", "is_primary_data"], key=None).assign(dataset=name)
     for name, ds in sources.items()],
    ignore_index=True,
)
print(design.groupby(["dataset", "disease"], observed=True).agg(
    cells=("donor_id", "size"), donors=("donor_id", "nunique"), primary=("is_primary_data", "mean"),
))
arms = design.groupby(["dataset", "donor_id"], observed=True)["disease"].nunique()
print("donors in more than one disease group:", int((arms > 1).sum()))
donors = design.groupby("dataset")["donor_id"].apply(set)
for a, b in itertools.combinations(donors.index, 2):   # shared IDs: same people, or a collision
    if shared := donors[a] & donors[b]:
        print(a, b, len(shared), "shared donor IDs")
```

Each study needs donors in every group you will compare; a group with fewer than two donors in a
study is descriptive only. Donors in two groups follow the rules of `cytearc-single-cell`
`references/integration-and-comparisons.md` ("A donor sampled in two arms").

### Compare studies without pooling counts

Harmonize labels through Cell Ontology IDs, summarize per donor within each study, and compare
the summaries side by side. This reads metadata only.

```python
term_ids = {row["term_id"] for row in catalog.list_terms("cell_type")
            if "plasmablast" in row["label"]}       # plasmablast and its Ig subtypes


def donor_shares(ds, terms, group_column="disease"):
    """Per-donor share of primary cells whose Cell Ontology ID is in `terms`."""
    meta = ds.cells.to_pandas_dataframe(
        ["donor_id", group_column, "cell_type_ontology_term_id", "is_primary_data"], key="I",
    )
    meta = meta[meta["is_primary_data"]]
    hit = meta["cell_type_ontology_term_id"].isin(terms)
    grouped = hit.groupby([meta[group_column], meta["donor_id"]], observed=True)
    return pd.DataFrame({"share": grouped.mean(), "cells": grouped.size()}).reset_index()


shares = pd.concat(
    [donor_shares(ds, term_ids).assign(dataset=name) for name, ds in sources.items()],
    ignore_index=True,
)
summary = shares.groupby(["dataset", "disease"], observed=True)["share"].agg(
    donors="count", median="median", low="min", high="max",
)
print(summary.round(4))
```

Report the per-study direction with its donor counts. Do not pool donors of different studies
into one test without a study term, and treat a pattern seen in one study only as unreplicated.
Exact donor-level tests are in `cytearc-single-cell` `references/integration-and-comparisons.md`.

### Build a composite for joint reanalysis

Select primary cells of the groups you need, then create the composite at a new local path.

```python
from pathlib import Path

from cytearc.composite import create_composite

rows = {}
for name, ds in sources.items():
    primary = ds.cells.fetch_all("is_primary_data")
    disease = ds.cells.fetch_all("disease")
    rows[name] = np.flatnonzero(primary & np.isin(disease, ["COVID-19", "normal"]))
    if rows[name].size == 0:
        raise ValueError(f"No primary COVID-19 or normal cells in {name!r}")

joint = create_composite(
    sources, at=Path("joint_cytebase.zarr"), features="intersection", rows=rows,
    mem_budget="6G", nthreads=4,
)
print(f"{joint.cells.N:,} cells and {joint.RNA.feats.N:,} shared genes")
joint_design = joint.cells.to_pandas_dataframe(["dataset", "orig_disease", "orig_donor_id"], key=None)
print(joint_design.groupby(["dataset", "orig_disease"], observed=True).agg(
    cells=("orig_donor_id", "size"), donors=("orig_donor_id", "nunique"),
))
```

Write the mapping `dataset_ids`, the release, and the selection rule into the provenance record
(`releases-and-provenance.md`). Map composite cells back to source cells through `dataset` and
`names` (the source cell IDs), or `ids`, never by position.

### Analyze the composite

Follow `cytearc-single-cell`. The composite-specific choices from the CyteArc tutorial: QC within
each dataset, the design columns frozen into every run, an explicit HVG blacklist, and a matched
baseline for any Harmony run.

```python
common = dict(
    assay="RNA",
    filtering={"method": "mad", "sample_column": "dataset", "n_mads": 5},   # QC within each study
    snapshot_columns=["dataset", "orig_disease", "orig_donor_id"],          # Harmony column first
    params={"species": "homo_sapiens", "hvg": {"blacklist": HUMAN_BLACKLIST}},
)   # HUMAN_BLACKLIST: the string in cytearc-single-cell references/gene-blacklists.md
baseline = joint.pipeline.run(label="joint_baseline", **common)
corrected = joint.pipeline.run(label="joint_harmony", harmony_batch_columns=["dataset"], **common)
assert baseline["pca"] == corrected["pca"]       # same cells and PCA; only the graph differs
retention = joint_design[["dataset", "orig_disease"]].assign(kept=baseline.cells.fetch_all("I"))
print(retention.groupby(["dataset", "orig_disease"], observed=True)["kept"].agg(["size", "mean"]))
```

Score mixing and preservation as in `integration-and-comparisons.md`. More mixing alone does not
establish a better result: studies differ in cohort, collection, and technology, and need not
share a composition. Draw condition conclusions from donor-level tests, not from the corrected
embedding.

### Reopen the composite later

```python
joint = cytearc.DataStore(
    "joint_cytebase.zarr", min_features_per_cell=-1, mem_budget="6G", nthreads=4,
    source_storage_options={name: {"token": False} for name in dataset_ids},  # anonymous reads
)
corrected = joint.pipeline.open(label="joint_harmony")
```

`source_storage_options` keys must be the source names given at creation. Credentials are never
stored in the composite.

## Parameters that matter

| Parameter | Default | Change when |
|---|---|---|
| `features` | required | `"intersection"` for pooled analysis; `"union"` only when absent genes are handled explicitly |
| `rows` | `None` (every stored cell) | always pass primary cells of the groups you need |
| `mem_budget`, `nthreads` | the smallest of the sources' budgets and workers | large selections, shared hosts |
| `filtering={"sample_column": "dataset"}` | pooled QC | always for pooled studies; audit retention per dataset and group |
| `harmony_batch_columns=["dataset"]` | `None` | only with a matched baseline and studies that each hold every compared group |
| `CYTEARC_SOURCE_CACHE_BYTES` | 2 GiB per open composite | lower for a small `TMPDIR`; `0` disables the cache |
| `source_storage_options` (reopen) | `None` | `{name: {"token": False}}` for anonymous reads |

## Check before moving on

- Every source is the same organism and measurement type, or the difference is recorded as a
  limitation; datasets of one collection were checked for shared donors.
- Only primary cells were selected, and each study holds donors in every compared group.
- The composite's cells and genes match expectations, and its design table counts donors per
  dataset and group.
- QC retention per dataset and group was audited; no study lost a population disproportionately.
- The provenance record names the release, the CyteBase IDs, the source names, and the selection.

## Pitfalls

- Different organisms share no feature IDs: `create_composite(features="intersection")` raises
  `ValueError: The composite feature space is empty`.
- `features="union"` fills genes missing from a study with zeros; HVGs and markers can then split
  studies by their gene annotation.
- Composite rows follow neither the `rows` order nor the source order, and sources interleave.
  Join by `ids` or by `dataset` plus `names`.
- `rows` are positions in the source's full table, not IDs; derive them from `fetch_all` arrays.
- Omitting `rows` pools every stored cell, including non-primary copies and unwanted groups (for
  example the influenza samples of one COVID-19 study).
- A mount passed as a source raises `ValueError: Mounted and composite sources are not supported`;
  an existing destination raises `FileExistsError`; reopen it with `cytearc.DataStore` instead.
- Reopening needs every source reachable and unchanged (`ValueError: Composite source identity
  changed`). Pinned release buckets keep sources stable; keep network access available.
- Harmony on `dataset` can remove real biology when tissues, cohorts, or condition balance differ
  between studies, and it runs silently on a confounded design. A study holding one condition only
  is confounded with it.
- Cell types differ in ontology depth and author vocabulary between studies (`plasmablast` against
  `IgG plasmablast`). Match by Cell Ontology ID or your own annotation, and keep author labels
  held out when they will judge the result.
- Pooled QC thresholds penalize studies with lower depth or another chemistry; filter per dataset.
- Per-cell statistics across studies treat cells as replicates. The unit is the donor, nested in its
  study.

## See also

- `catalog-search.md`: SQL over the catalog and label lookups.
- `releases-and-provenance.md`: recording sources and composite bindings.
- `cytearc-single-cell` `references/integration-and-comparisons.md`, `references/quality-control.md`,
  `references/gene-blacklists.md`, and `references/performance-and-export.md`.

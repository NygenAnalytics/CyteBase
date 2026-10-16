# Catalog search

Find datasets in a CyteBase release, read their catalog rows and build records, and query the
catalog with SQL. Nothing here opens a DataStore or reads counts.

## When to use

- Choosing datasets by topic, author, tissue, disease, organism, assay, cell type, or size.
- Checking a dataset's citation, labels, primary cells, and counts source before opening it.
- Building a shortlist for cross-dataset work (`cross-dataset.md`).

## Key concepts

- The catalog is a DuckDB file published in each release bucket. `Catalog()` downloads it, verifies
  its SHA-256, and keeps one copy in `~/.cytearc/cytebase.duckdb` (Windows:
  `%LOCALAPPDATA%\cytearc\cytebase.duckdb`). Every query checks the published checksum again
  (about a second on a good connection), so queries need network access.
  `catalog.connect_catalog()` runs several statements under one check.
- Tables:
  - `datasets`, one row per dataset. Identity: `cytebase_id`, `dataset_id` (CELLxGENE stable ID),
    `collection_id`, `latest_version_id`, `processed_version_id` (the CELLxGENE dataset version that
    was converted). Description: `title`, `citation`, `doi`, `first_author`, `year`,
    `cellxgene_url`, `explorer_url`. Label lists: `organism_labels`, `assay_labels`,
    `tissue_labels`, `organ_labels`, `disease_labels`, `cell_type_labels`, `sex_labels`,
    `development_stage_labels`, `suspension_types`; ontology IDs in `organism_ids`, `assay_ids`,
    `tissue_ids`, `organ_ids`, `disease_ids`, `cell_type_ids`. Size: `cell_count`,
    `primary_cell_count`, `n_genes`, `mean_genes_per_cell`. Build: `status`, `zarr_uri`,
    `h5ad_uri`, `schema_version`, `pipeline_version`, `registered_at`, `processed_at`.
  - `dataset_terms`, one row per dataset, facet, and term: `cytebase_id`, `facet`, `term_id`,
    `label`, `label_rank` (natural sort order). Holds term IDs for every facet, including `sex` and
    `development_stage`, which have no `*_ids` column in `datasets`.
  - `collections`, one row per CELLxGENE collection (study): `collection_id`, `name`,
    `description`, `doi`, `first_author`, `year`, `journal`, `consortia`, `n_datasets_total`,
    `n_datasets_main`, `skipped_dataset_ids`, `skipped_dataset_reasons`, `registered_at`.
- **Ready** means `status = 'ready' AND processed_version_id = latest_version_id AND zarr_uri IS NOT
  NULL`: a verified store exists for the dataset's latest registered CELLxGENE version. `search` and
  `find_datasets` apply it by default (`ready_only=True`), `query` applies nothing, and `list_terms`
  counts every registered dataset. In `2610` all 1,372 datasets are ready.
- **Facets**: `tissue`, `organ`, `disease`, `assay`, `organism`, `cell_type`, `sex`,
  `development_stage`, and `suspension_type` (column `suspension_types`). Each label list is the
  union over the dataset's cells. `organ` is in the schema but has no terms in `2610`.
- `search(text)` keeps datasets whose ID, title, citation, first author, or any facet label contains
  every whitespace-separated word, as a case-insensitive substring. `find_datasets(**facets)` keeps
  datasets whose label lists contain one of the given exact labels for every facet: AND across
  facets, OR within a list. Both order by `cell_count` descending, then ID. `search` returns at most
  50 rows by default; `find_datasets` has no limit.
- Results are `CatalogResults` (`cytebase.display.CatalogResults`): a `list` of complete row
  dictionaries with a Markdown display. The display shows 20 rows, shortens cells to 100
  characters, and escapes Markdown characters; the dictionaries keep full values. Slicing returns a
  plain list.
- A `DatasetEntry` (`catalog.dataset(id)`) holds the catalog row (`entry.row`, with shortcuts `id`,
  `title`, `citation`, `cell_count`) and fetches the published build record on demand
  (`entry.record()`, cached on the entry). It never opens a store.

## Recipes

### Search by words, then read rows

```python
import cytearc
import cytebase

cytearc.configure_output(level="WARNING", progress=False)
catalog = cytebase.Catalog(version="2610")

hits = catalog.search("kidney cortex", limit=10)  # every word as a substring of some field
print(len(hits), hits.to_markdown(columns=["cytebase_id", "title", "cell_count"], max_cell_chars=40))
ids = [row["cytebase_id"] for row in hits]        # full values; never copy from the table
first = hits[0]                                   # a dict with every catalog column
print(first["first_author"], first["year"], first["primary_cell_count"], first["suspension_types"])
```

### Filter by exact labels

```python
print(catalog.list_terms("tissue").to_markdown(max_rows=10))  # label, ontology ID, datasets
tissues = {row["label"] for row in catalog.list_terms("tissue")}
assert "blood" in tissues                         # labels are exact and case-sensitive
blood = catalog.find_datasets(
    tissue="blood", organism="Homo sapiens", suspension_type=["cell", "nucleus"],
)                                                 # AND across facets, OR within a list
print(len(blood), sum(row["primary_cell_count"] for row in blood))
```

`list_terms()` without a facet lists every facet (with a `facet` column). Its `n_datasets`
counts registered datasets, ready or not.

### Query with SQL and bound parameters

Bind every value with `?` and a list (or `$name` and a dict); list columns take list
parameters. `list_has_any` is what `find_datasets` uses; `list_has_all` requires every label.

```python
READY = "status = 'ready' AND processed_version_id = latest_version_id AND zarr_uri IS NOT NULL"
covid_blood = catalog.query(
    f"""
    SELECT cytebase_id, collection_id, first_author, year, cell_count, primary_cell_count,
           assay_labels, suspension_types
    FROM datasets
    WHERE {READY}
      AND list_has_any(organism_labels, ?)
      AND list_has_any(tissue_labels, ?)
      AND list_has_all(disease_labels, ?)
    ORDER BY cell_count DESC
    """,
    parameters=[["Homo sapiens"], ["blood"], ["COVID-19", "normal"]],
)
print(len(covid_blood))                           # datasets with both COVID-19 and normal cells

by_term = catalog.query(                          # an ontology ID instead of a label
    "SELECT DISTINCT cytebase_id FROM dataset_terms WHERE facet = ? AND term_id = ?",
    parameters=["tissue", "UBERON:0000178"],
)
one = catalog.query("SELECT cytebase_id, cell_count FROM datasets WHERE cytebase_id = $id",
                    {"id": ids[0]})
studies = catalog.query(                          # datasets per study, with journal and consortia
    """
    SELECT c.collection_id, c.name, c.journal, c.consortia,
           count(*) AS n_datasets, sum(d.primary_cell_count) AS primary_cells
    FROM datasets AS d JOIN collections AS c USING (collection_id)
    WHERE list_has_any(d.tissue_labels, ?)
    GROUP BY ALL ORDER BY primary_cells DESC
    """,
    parameters=[["blood"]],
)
```

### Run several statements under one checksum check

```python
with catalog.connect_catalog() as con:            # read-only DuckDB connection; closed on exit
    print(con.execute("SHOW TABLES").fetchall())
    sizes = con.execute(
        "SELECT cytebase_id, cell_count FROM datasets WHERE list_has_any(tissue_labels, ?)",
        [["blood"]],
    ).df()                                        # a pandas DataFrame
```

### Read facts about one dataset without opening it

```python
entry = catalog.dataset(ids[0])                   # KeyError for an unknown ID
print(entry.describe())                           # citation, links, size, labels, source embeddings
row = entry.row                                   # the complete catalog row
print(row["primary_cell_count"], row["cell_count"], row["assay_labels"], row["suspension_types"])
record = entry.record()                           # published dataset.json, fetched once, cached
inspection = record["inspection"]
print(inspection["countsLocation"], inspection["countsIntegerLike"], inspection["isPrimaryDataCounts"])
print(record["buildReceipt"]["verifiedAt"], record["buildReceipt"]["verification"]["countsDtype"])
print(entry.source_embeddings())                  # every source obsm key, imported or not
```

`countsLocation` is the source matrix the counts came from (`raw/X`, `X`, or a counts layer),
`isPrimaryDataCounts` splits the source cells by `is_primary_data`, and
`verification.countsDtype` is the stored count dtype. In a notebook, displaying `entry` renders
`describe()`.

### Tabulate results

```python
import pandas as pd

frame = pd.DataFrame(list(blood))                 # every column, full values
print(blood.to_markdown(columns=["cytebase_id", "cell_count"], max_rows=None, max_cell_chars=None))
```

## Parameters that matter

| Parameter | Default | Change when |
|---|---|---|
| `Catalog(version=)` | `None`: `CYTEBASE_BUCKET` if set, else the latest release | always pin it for reproducible work |
| `Catalog(bucket=)` | `None` | a bucket outside the public releases, as `namespace/name` or `hf://buckets/namespace/name`; never with `version=` |
| `Catalog(token=)` | `None`: a Hugging Face login if present, else anonymous | `False` forces anonymous access |
| `search(limit=)` | `50` | `None` for every match |
| `search` / `find_datasets` `ready_only=` | `True` | `False` to see registered datasets without a ready store |
| `max_cell_chars=` (queries, `list_terms`) | `100` | `None` displays full values; rows are never shortened |
| `to_markdown(columns=, max_rows=, max_cell_chars=)` | display columns, `20`, `100` | pick columns; `max_rows=None` shows every row |
| `query(sql, parameters=)` | `None` | `?` placeholders with a list, or `$name` with a dict |

## Check before moving on

- Every kept ID came from `row["cytebase_id"]`, and `catalog.dataset(id)` resolves it.
- Every filter label appears exactly in `catalog.list_terms(facet)`.
- `entry.row["status"] == "ready"` and `processed_version_id == latest_version_id`.
- `primary_cell_count`, `suspension_types`, `assay_labels`, and
  `record()["inspection"]["countsLocation"]` fit what the analysis assumes.

## Pitfalls

- Printed tables replace Markdown characters such as `_`, `*`, `|`, `'`, and `<` with HTML entities
  (`_` shows as `&#95;`) and shorten long cells. Read values from the row dictionaries.
- `search` is substring matching on every word: `T`, `B`, or `NK` match nearly all datasets
  (`search("T cell")` matched all 1,372 in `2610`). Use longer words, or `cell_type=` with exact
  labels.
- Words can match in different fields and results are ordered by size. In `2610`,
  `search("kidney cortex")` ranks an 11-million-nucleus mouse embryo atlas first, because its cell
  type labels include `kidney collecting duct principal cell` and `cerebral cortex endothelial
  cell`. Check `organism_labels`, `tissue_labels`, and the title of every hit.
- Labels are exact and not ontology-aware: `find_datasets(cell_type="plasmablast")` misses datasets
  that only use `IgG plasmablast`. List the related labels from `list_terms` and pass them as a
  list, or query `dataset_terms` by term ID.
- Cells annotated with several diseases carry a compound label such as
  `HIV infectious disease || leishmaniasis` (94 such disease labels in `2610`). A filter on one
  disease does not match them.
- `find_datasets(organ=...)` always returns nothing in `2610`; use `tissue`.
- The catalog includes spatial datasets (Visium Spatial Gene Expression V1, Slide-seqV2, MERFISH),
  whose `suspension_types` is `na`. Filter `suspension_type=["cell", "nucleus"]` for dissociated
  cells, and keep cells and nuclei apart unless the question allows both.
- Dataset-level labels say only that some cells carry them. A dataset listing `COVID-19` and
  `normal` may have few donors in one group; count donors after opening.
- `cell_count` includes non-primary cells. `primary_cell_count` counts cells marked
  `is_primary_data`, the canonical copy of each cell across CELLxGENE; the other cells also appear
  in another dataset (106 datasets in `2610` hold such cells).
- One collection can contribute many datasets (one `2610` collection has 128), often subsets of
  one study with shared donors, sometimes independent studies republished together. Group by
  `collection_id` and check donors before counting studies (`cross-dataset.md`).
- `connect_catalog()` returns a connection you must close; use a `with` block.
- The local cache holds one catalog file for all releases. Alternating catalogs of two releases
  downloads the catalog again on each switch; use one release per process.
- There is no offline mode: a query without network access fails even when a cached catalog exists.

## See also

- `cross-dataset.md`: turning a shortlist into comparable datasets.
- `open-and-mount.md`: opening the chosen dataset.
- `releases-and-provenance.md`: pinning the release and recording entry fields.

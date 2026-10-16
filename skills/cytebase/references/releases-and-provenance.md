# Releases and provenance

Pin a CyteBase release, record which build every dataset came from, read mount receipts and
composite bindings, and tell whether data changed between sessions or releases.

## When to use

- Before the first query of any analysis that must be reproducible.
- Reopening a mount or composite in a later session.
- Writing a report, figure legend, or handoff that names its data.
- Comparing or repeating a result in a newer release.

## Key concepts

- `cytebase.releases()` returns every public release, newest first. Each `Release` has `version`,
  `released` (`YYYY-MM`), `notes`, `changelog`, `bucket` (`Nygen/cytebase-<version>`), and `latest`
  (the release `Catalog()` opens by default). `2610` is the first versioned release.
- Versions are `YYMM`, or `YYMM.N` for a later release in the same month: `Catalog(version="2610.1")`
  opens `Nygen/cytebase-2610.1`. `Catalog` resolves its bucket from `bucket=`, then `version=`, then
  the `CYTEBASE_BUCKET` environment variable, then the latest release; `bucket=` and `version=`
  together raise `ValueError`.
- The release list ships inside the installed package. Upgrading `cytebase` can change what a bare
  `Catalog()` opens; a pinned `version=` does not change.
- Each release is its own bucket and is meant to stay fixed once published, so rerunning against a
  pinned release should reproduce its catalog results and data; the checks below detect a change.
  A newer release can add, update, rebuild, or drop datasets, with a newer CELLxGENE dataset
  version or build pipeline. Do not assume that a CyteBase ID, a dataset version, or a cell set
  carries over between releases; match datasets by CELLxGENE identity (`dataset_id`) and compare
  `processed_version_id` and `sourceSha256`.
- Every open verifies the dataset's build record against its store. A mount's receipt pins one
  build; a composite's source bindings pin each source's fingerprints. Either refuses to reopen
  against a changed source.

| Field | Where | Identifies |
|---|---|---|
| release version, bucket | `Release.version`, `Release.bucket`; also inside `zarr_uri` | the catalog snapshot and storage |
| `cytebase_id` | `entry.id` | the dataset within a release |
| `dataset_id` | `entry.row` | the CELLxGENE dataset, across its versions |
| `processed_version_id` | `entry.row` | the exact CELLxGENE dataset version converted |
| `collection_id` | `entry.row` | the CELLxGENE collection (study) |
| `zarr_uri` | `entry.row` | the published store, including its bucket |
| `pipeline_version`, `processed_at` | `entry.row` | the build code revision and build time |
| `schema_version` | `entry.row` | the CELLxGENE schema of the source (`7.1.0` throughout `2610`) |
| `sourceSha256`, `sourceUrl`, `countsLocation` | `entry.record()["inspection"]` | the source H5AD and the matrix converted |
| `verifiedAt`, `verification` | `entry.record()["buildReceipt"]` | when and how the stored arrays were checked |
| receipt | `<mount>.cytebase.json` | the build a mount is pinned to |
| source bindings | composite root attribute `composite`, key `sources` | each composite source's location and fingerprints |

## Recipes

### Pin a release

```python
import cytearc
import cytebase

cytearc.configure_output(level="WARNING", progress=False)
for release in cytebase.releases():               # newest first
    print(release.version, release.released, release.bucket, release.latest, release.notes)
VERSION = "2610"                                  # write it into the analysis log now
release = next(r for r in cytebase.releases() if r.version == VERSION)
catalog = cytebase.Catalog(version=VERSION)
```

### Record dataset provenance

Write this record before analysis and keep it with the results.

```python
import json
from importlib.metadata import version as package_version
from pathlib import Path


def provenance(entry):
    row, record = entry.row, entry.record()
    return {
        "cytebaseId": entry.id,
        "zarrUri": row["zarr_uri"],
        "cellxgeneDatasetId": row["dataset_id"],
        "cellxgeneVersionId": row["processed_version_id"],
        "collectionId": row["collection_id"],
        "schemaVersion": row["schema_version"],
        "pipelineVersion": row["pipeline_version"],
        "processedAt": row["processed_at"].isoformat(),
        "sourceSha256": record["inspection"]["sourceSha256"],
        "sourceUrl": record["inspection"]["sourceUrl"],
        "countsLocation": record["inspection"]["countsLocation"],
        "verifiedAt": record["buildReceipt"]["verifiedAt"],
        "cells": row["cell_count"],
        "primaryCells": row["primary_cell_count"],
        "citation": entry.citation,
        "doi": row["doi"],
    }


ids = ["wilk_2020_single_cell_atlas_peripheral_sars_cov_2_infection_456e8b9b"]
saved = {
    "release": release.version,
    "bucket": release.bucket,
    "packages": {name: package_version(name) for name in ("cytebase", "cytearc")},
    "datasets": {cid: provenance(catalog.dataset(cid)) for cid in ids},
}
Path("cytebase_provenance.json").write_text(json.dumps(saved, indent=2))
```

### Read a mount's receipt and reopen it with its release

The receipt names no release, but its `zarrUri` contains the bucket.

```python
import re

RELEASE_URI = re.compile(r"^hf://buckets/Nygen/cytebase-(\d{4}(?:\.[1-9]\d*)?)/")

receipt = json.loads(Path("work/wilk.zarr.cytebase.json").read_text())
print(receipt["cytebaseId"], receipt["processedVersionId"], receipt["verifiedAt"])
match = RELEASE_URI.match(receipt["zarrUri"])     # None for a bucket outside the public releases
mount_catalog = cytebase.Catalog(version=match.group(1))
analysis = mount_catalog.mount_datastore(receipt["cytebaseId"], at="work/wilk.zarr")
```

### Record a composite's sources

The composite records each source's location and fingerprints in its root `composite` attribute;
reading it read-only changes nothing.

```python
import zarr

bindings = zarr.open_group("joint_cytebase.zarr", mode="r").attrs["composite"]["sources"]
for binding in bindings:
    match = RELEASE_URI.match(binding["location"])
    print(binding["name"], binding["location"], match.group(1) if match else "not a public release")
```

Record the mapping from source names to CyteBase IDs and the row-selection rule yourself when you
create the composite; the bindings hold locations, not your selection.

### Check whether data changed

Within a pinned release, nothing in the record should differ. In another release, find the same
CELLxGENE dataset by its stable ID, then compare versions and checksums.

```python
saved = json.loads(Path("cytebase_provenance.json").read_text())
fields = ("cellxgeneVersionId", "sourceSha256", "verifiedAt", "zarrUri")
for cid, before in saved["datasets"].items():
    now = provenance(catalog.dataset(cid))
    print(cid, [f for f in fields if before[f] != now[f]] or "unchanged")

other = cytebase.Catalog(version=VERSION)         # replace with the release to compare against
for cid, before in saved["datasets"].items():
    same = other.query(
        "SELECT cytebase_id, processed_version_id FROM datasets WHERE dataset_id = ?",
        parameters=[before["cellxgeneDatasetId"]],
    )
    print(cid, [(r["cytebase_id"], r["processed_version_id"] == before["cellxgeneVersionId"]) for r in same])
```

### Cite the data

`entry.citation` holds the publication link, the CELLxGENE dataset version, and its collection;
`entry.row["doi"]` holds the study DOI. Cite the original study and CZ CELLxGENE Discover (CZI
Cell Science Program et al., Nucleic Acids Research 2025, doi:10.1093/nar/gkae1142), and name the
CyteBase release and IDs in methods text.

## Parameters that matter

| Parameter | Default | Change when |
|---|---|---|
| `Catalog(version=)` | `None` (environment, then latest) | always pin it |
| `Catalog(bucket=)` | `None` | a private or test bucket; record it in place of a version |
| `CYTEBASE_BUCKET` | unset | it redirects a bare `Catalog()`; unset it or pin `version=` |

## Check before moving on

- The analysis log names the release version, and every dataset has a provenance record written
  before the analysis started.
- Each mount's receipt `zarrUri` names the pinned release; composites record source names, IDs, and
  selection rules.
- Figures and tables cite the study and CELLxGENE Discover.

## Pitfalls

- A bare `Catalog()` silently follows `CYTEBASE_BUCKET` or the newest release known to the installed
  package. Results then depend on the environment.
- An unpublished version string passes the format check and then fails at the first request with
  an HTTP error from `huggingface_hub` (`401 Unauthorized` for anonymous access).
- Reopening a mount through a catalog of another release raises `ValueError` ("This mount refers to
  a different dataset build"); use the release in the receipt's `zarrUri`.
- `processed_at` and `registered_at` are timezone-aware `datetime` values; serialize them with
  `.isoformat()`.
- A repacked copy has no receipt and no `matrixSource`. Copy the receipt into the provenance record
  before repacking.
- One local catalog file serves every release. Use one release per process: alternating releases
  downloads the catalog again each time.
- Mixing releases in one composite is possible but makes the analysis depend on two snapshots;
  open every source from one pinned catalog unless the comparison is the point.

## See also

- `open-and-mount.md`: receipts and reopen rules.
- `cross-dataset.md`: composites and their sources.
- `cytearc-single-cell` `references/pipeline-runs-and-artifacts.md`: the CyteArc handoff record.

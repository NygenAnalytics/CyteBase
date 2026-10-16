# CyteBase

<p align="left">
  <a href="https://github.com/NygenAnalytics/CyteBase/actions/workflows/pytest.yml"><img src="https://github.com/NygenAnalytics/CyteBase/actions/workflows/pytest.yml/badge.svg" alt="Tests"></a>
  <a href="https://pypi.org/project/cytebase"><img src="https://img.shields.io/pypi/v/cytebase.svg?color=4c72b0" alt="PyPI"></a>
  <a href="https://pypi.org/project/cytebase"><img src="https://img.shields.io/badge/python-3.13%20%7C%203.14%20%7C%203.15-4c72b0.svg" alt="Python 3.13, 3.14, and 3.15"></a>
</p>

CyteBase is a **searchable catalog of public single-cell datasets stored as cloud-hosted
[CyteArc](https://github.com/NygenAnalytics/CyteArc) DataStores**. Search by study, tissue,
disease, organism, or cell type, inspect a dataset's metadata and published embeddings, then
open it read-only or mount it for your own analysis. Counts stay remote on
[Hugging Face](https://huggingface.co/Nygen), and every result you compute is saved in a store you
control. Public access needs no credentials.

Each release is a CELLxGENE Discover snapshot converted to CyteArc stores and published in its
own bucket. The current release, `2610`, holds the primary RNA datasets of 376
registration-ready collections from the snapshot taken on 2026-10-10.

## Install

Python 3.13 or newer.

```bash
pip install cytebase
```

CyteBase installs CyteArc. Install `cytearc[extra]` as well to plot datasets with `ds.plots`.

## Quick start

```python
import cytebase

catalog = cytebase.Catalog()  # the latest public release, read anonymously
matches = catalog.search("kidney")
print(matches)

# Open one of the matching datasets for read-only exploration.
dataset_id = matches[0]["cytebase_id"]
ds = catalog.open_datastore(dataset_id)

# Create a writable local store for your own analysis, keeping counts remote.
analysis = catalog.mount_datastore(dataset_id, at="kidney_analysis.zarr")
```

`analysis` is a CyteArc `DataStore`: run the CyteArc pipeline on it to save new results locally
while count blocks are read over the network as needed. `cytebase.releases()` lists the public
releases, and `cytebase.Catalog(version="2610")` opens a specific one, so a result can name the
exact release it came from.

Read the [documentation](https://docs.nygen.io/CyteBase/) for catalog filters, SQL queries,
embeddings, mounts, and case studies.

## Working with CyteArc

CyteBase depends on CyteArc, which opens and analyzes the datasets: read-only DataStores,
mounts for your own results, and composite stores that analyze several remote datasets together
without copying their counts. CyteArc does not depend on CyteBase. Each dataset is a CyteArc
store at a Hugging Face URI, the catalog's `zarr_uri`, so CyteArc alone can open it too, as the
[CyteArc documentation](https://docs.nygen.io/CyteArc/tutorials/cytebase-datasets) shows.

## Repository layout

- `cytebase/`: the SDK published to PyPI.
- `cytebase/pipeline/`: the Modal pipeline that ingests CELLxGENE datasets, converts and verifies
  them, and publishes the catalog. It runs from a checkout and is not part of the wheel.
- `docs/`: the documentation site.
- `skills/cytebase/`: the agent skill for using CyteBase.
- `tests/`: the test suite.

Contributors and coding agents start with [AGENTS.md](AGENTS.md).

## License

BSD 3-Clause. See [LICENSE](LICENSE). Dataset licenses and citations come from their sources;
each catalog entry records its citation.

---
description: Install the CyteBase SDK with Python 3.13 or newer, add CyteArc's plotting dependencies, and choose a public release, bucket, and credentials.
---

(installation)=
# Installation

CyteBase requires Python 3.13 or newer. Installing the `cytebase` package also installs
[CyteArc](https://docs.nygen.io/CyteArc/), which opens and analyzes the datasets, DuckDB for
catalog queries, and the Hugging Face client for bucket access.

## Install with uv

Run these commands in the directory where you will work.
[uv](https://docs.astral.sh/uv/) creates an isolated `.venv` there:

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install cytebase
```

In Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1` instead.

With pip, create and activate a virtual environment whose Python is version 3.13 or newer,
then install the package:

```bash
python -m pip install cytebase
```

```{note}
CyteArc depends on `hnswlib`, which the installer compiles from source, so the installation
needs a C++ compiler. The [CyteArc installation guide](https://docs.nygen.io/CyteArc/installation)
lists the compiler for each platform and a conda alternative for Windows.
```

(installation_plotting)=
## Plotting

Plotting calls such as `ds.plots.embedding` use CyteArc's plotting module, which needs
CyteArc's `extra` optional dependencies, including matplotlib and seaborn. The tutorials use
them:

```bash
uv pip install cytebase "cytearc[extra]"
```

Without them, a plotting call raises an `ImportError` that names `cytearc[extra]`.

## Verify the installation

`import cytebase` defers loading its modules, so the check imports `Catalog`, which also loads
CyteArc, and prints both versions:

```bash
python -c "from importlib.metadata import version; from cytebase import Catalog; print(version('cytebase'), version('cytearc'))"
```

To use the notebooks, install and launch JupyterLab from the same environment:

```bash
uv pip install jupyterlab
jupyter lab
```

## Releases and buckets

Each public CyteBase release is a read-only Hugging Face bucket named by year and month,
`Nygen/cytebase-YYMM`. A later release in the same month adds a patch number, as in
`Nygen/cytebase-2610.1`. `cytebase.releases()` lists the public releases, newest first:

```python
import cytebase

for release in cytebase.releases():
    print(release.version, release.bucket, release.released, release.latest)
```

`Catalog()` opens the release marked `latest`, currently `2610` in `Nygen/cytebase-2610`. Pin a
release to reproduce discovery results:

```python
catalog = cytebase.Catalog(version="2610")
```

To use another bucket, pass `bucket=` or set the `CYTEBASE_BUCKET` environment variable before
starting Python. Both accept `namespace/name` or `hf://buckets/namespace/name`. The catalog
takes its bucket from `bucket=`, then `version=`, then `CYTEBASE_BUCKET`, then the latest
release. Passing both `bucket=` and `version=` raises an error.

## Credentials

Public releases need no credentials. With the default `token=None`, CyteBase uses your Hugging
Face credentials when they are available, such as an `HF_TOKEN` environment variable or a login
with `hf auth login`, and reads anonymously otherwise. `token=False` always reads anonymously,
and a token string reads with that token. A private bucket needs a token with access to it.
Keep tokens and private bucket names out of notebook source and outputs.

Anonymous Hugging Face access allows 500 API requests per 5 minutes per IP address, and opening
a store and reading its metadata uses a share of them. After a `429 Too Many Requests` error,
wait for the window to reset, or sign in with `hf auth login` for a higher limit.

## Network access

CyteBase reads from Hugging Face over HTTPS. Behind a firewall or proxy, the Python process
needs access to the Hugging Face Hub.

- **Catalog.** `Catalog()` downloads the DuckDB catalog and keeps one verified copy at
  `~/.cytearc/cytebase.duckdb`, or `%LOCALAPPDATA%\cytearc\cytebase.duckdb` on Windows. Every
  new query compares that copy with the published SHA-256 checksum and downloads the catalog
  again when it has changed, so queries need network access even when a copy is cached.
- **DataStores.** Opened and mounted stores read metadata and count blocks from the bucket as
  needed. CyteBase keeps no persistent local copy of the counts.
- **Mounts.** `mount_datastore` writes new analysis results to a local path, but its counts
  stay remote, so later reads also need network access.

## Install from source

Clone the repository and let uv create the project environment:

```bash
git clone https://github.com/NygenAnalytics/CyteBase.git
cd CyteBase
uv sync
```

The checkout's default environment also includes the test tools and the dependencies of the
operator-only [build pipeline](developers/build_pipeline.md).

## Troubleshooting

- **`Catalog(version=...)` fails with an unexpected keyword argument:** the code imported
  CyteArc 1.1's earlier copy of the SDK, `cytearc.cytebase`. Import `cytebase` instead.
- **A plotting call raises an `ImportError` naming `cytearc[extra]`:** install CyteArc's plotting
  dependencies as described in {ref}`Plotting <installation_plotting>`.
- **`429 Too Many Requests`:** wait for the anonymous request window to reset, or sign in with
  `hf auth login`.
- **CyteBase imports in a terminal but not in a notebook:** compare
  `python -c "import sys; print(sys.executable)"` with the notebook kernel, then launch Jupyter
  from the environment that contains CyteBase or select its kernel.

## Next steps

Follow [](tutorials/cytebase.ipynb) to search the catalog and plot a published dataset.

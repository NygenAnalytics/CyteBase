---
description: Deploy and operate the Modal pipeline that ingests CELLxGENE datasets and builds CyteBase catalogs. For CyteBase operators.
---

# Build pipeline

`cytebase.pipeline` ingests CELLxGENE datasets and builds the CyteBase catalog through
[Modal](https://modal.com). It is for CyteBase operators: it runs from a repository checkout
and is not part of the published `cytebase` package. Searching and opening datasets never
needs it.

A deployment writes to the bucket that its `cytearc-env` Modal secret names, or to the public
release bucket that `--bucket-version` selects. Its HTTP API can register collections, start
dataset processing, and rebuild the catalog with the deployment's Hugging Face credentials.

## Environment

In a checkout, `uv sync` installs the pipeline's dependencies, which belong to the default
`pipeline` dependency group. Modal does not import on Python 3.15, so that group omits Modal
there.

## Deploy

Deploy with the supported command:

```bash
uv run python -m cytebase.pipeline.deploy --env <environment>
```

The command validates a supplied `CYTEBASE_PIPELINE_VERSION`, or resolves the Git revision,
before it runs `modal deploy` for the `cytebase.pipeline.app` module. It always sets the bucket
key and version, so values left in the shell never select the development bucket or another
release. Invoking the Modal app directly bypasses this preparation, and the caller must then
supply a nonblank `CYTEBASE_PIPELINE_VERSION`.

| Option | Effect |
| --- | --- |
| `-e`, `--env` | Modal environment; Modal's default when omitted |
| `--dev` | Use the bucket named by `CYTEBASE_BUCKET_DEV` in the `cytearc-env` secret |
| `--bucket-version` | Use the release bucket `Nygen/cytebase-VERSION`, for example `2610.1` |
| `--process-containers` | Dataset worker container limit |
| `--download-connections` | Source connections, 1 to 4 |
| `--hub-api-quota` | Hub API calls the token's account may make per five minutes (default 1000); dataset starts are paced to stay under it |
| `--dry-run` | Print the deployment without running it |

`--dev` and `--bucket-version` cannot be combined.

## Buckets and releases

By default, a deployment writes to the bucket that `CYTEBASE_BUCKET` names in the
`cytearc-env` secret. `--bucket-version 2610.1` writes to the public release bucket
`Nygen/cytebase-2610.1` instead, and the secret then needs only `HF_TOKEN`. The app and its run
state belong to the Modal environment, not the bucket, so drain any active run before
deploying another bucket version to the same environment.

The SDK chooses its bucket separately: `cytebase.Catalog()` opens the release that
`cytebase.releases()` marks as latest.

## Modal secrets

The target environment needs two Modal secrets, and a deployment fails while either is
missing:

- `cytearc-env` holds `HF_TOKEN` and the bucket key, `CYTEBASE_BUCKET`, or
  `CYTEBASE_BUCKET_DEV` for `--dev`. With `--bucket-version`, it needs only `HF_TOKEN`.
- `cytebase-api` holds `CYTEBASE_API_TOKEN`, at least 32 visible ASCII characters without
  whitespace. Only the web function receives it.

Every environment needs both secrets, including one whose operators never call the HTTP API
and start work only with `python -m cytebase.pipeline reset-run` or the Modal SDK: the app
always deploys its web function with the workers. Create the API secret in each environment
from a private dotenv file kept outside the repository:

```bash
python -c "import secrets; print('CYTEBASE_API_TOKEN=' + secrets.token_urlsafe(32))" > <file>
modal secret create cytebase-api --from-dotenv <file> --env <environment>
```

To rotate the token, recreate the secret with `--force` and redeploy. Keep both tokens out of
source control, notebooks, and shell history.

## HTTP API

Every request to the deployed HTTP API passes two checks:

1. **Modal proxy authentication.** Create a proxy auth token in the Modal workspace that owns
   the app, for example with `modal workspace proxy-tokens create`, and send its ID and secret
   in the `Modal-Key` and `Modal-Secret` headers. Modal rejects a request without them before
   it reaches the app. A proxy token is valid for every proxy-authenticated endpoint of the
   workspace, so on its own it does not identify a CyteBase operator.
2. **The API token.** Send the `CYTEBASE_API_TOKEN` value in the `Cytebase-Token` header. The
   app answers 401 to any request without it, before routing or reading the body. The
   `Authorization` header is not used because Modal's proxy reads it for its own bearer tokens.

The API serves no OpenAPI schema or documentation pages (`/openapi.json`, `/docs`, `/redoc`).

`GET /jobs/{call_id}` reports only calls that this deployment's API started. The API records
each call under the key `api:<call ID>` of the `cytebase-runs` Modal Dict of its environment and
answers 404 for any other ID, including calls that `reset-run` or the Modal SDK started; poll
those through the Modal SDK. Modal expires a Dict entry 7 days after its last read or write, so
the API reports a call for 7 days after it started or was last polled, whichever is later. Modal
also keeps a call's result only for a limited time, after which the API answers 404 with "Job
result is missing or expired".

## Local commands

`python -m cytebase.pipeline` runs local inspection, conversion, collection discovery, and
explicit run reset. Each command prints its result as JSON on standard output and its
diagnostics on standard error.

| Command | Purpose |
| --- | --- |
| `inspect SOURCE [--raw-data-location {X,raw.X}]` | Inspect and validate a local H5AD |
| `convert SOURCE --manifest MANIFEST --output OUTPUT` | Convert a local H5AD with its full inspection manifest |
| `collection-ids` | List public CELLxGENE collection IDs |
| `inventory --output OUTPUT [--bucket BUCKET]` | Save a public collection inventory with primary RNA selection, optionally joined with a verified CyteBase catalog snapshot |
| `reset-run --expected-run-id ID --workers-drained [--env ENVIRONMENT]` | Reset an interrupted run only after draining its workers |

`convert` writes `data.zarr` and its `cytearc_ingest.json` result to the output directory and
verifies a completed store. `reset-run` asks the deployed `cytebase` app in the given Modal
environment to reset the run and prints the call ID.

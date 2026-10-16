import os

# Bound CyteArc worker auto-detection before pytest plugins import NumPy or CyteArc.
os.environ["CYTEARC_WORKERS"] = "2"
# Interactive backends such as TkAgg bind figures to the thread that created
# them. Garbage collection triggered on a Zarr I/O thread then finalizes those
# objects on the wrong thread and crashes the worker with an illegal instruction.
os.environ["MPLBACKEND"] = "Agg"

import sys

import pytest
import zarr
from threadpoolctl import threadpool_limits

from cytearc.utils import configure_output, logger

pytest_plugins = ["tests.fixtures_cytebase"]


@pytest.fixture(scope="session", autouse=True)
def _limit_blas_threads():
    with threadpool_limits(limits=1, user_api="blas"):
        yield


@pytest.fixture(scope="session", autouse=True)
def _quiet_test_logs() -> None:
    """Keep pytest output readable while standalone CLIs retain INFO logs."""
    configure_output(progress=False)
    logger.remove()
    logger.add(sys.stderr, level="ERROR")


def _reset_zarr_runtime() -> None:
    """Restore Zarr's process defaults so the next storage call plans afresh."""
    from cytearc.storage import async_execution

    zarr.config.set({"threading.max_workers": None, "async.concurrency": 10})
    async_execution._HOST_THREAD_CEILING = None


@pytest.fixture(autouse=True)
def _fresh_zarr_runtime() -> None:
    _reset_zarr_runtime()
    yield
    _reset_zarr_runtime()

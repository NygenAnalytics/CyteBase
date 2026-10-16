"""The ``cytebase`` package resolves its SDK objects lazily."""

import pytest

import cytebase


def test_lazy_exports_import_and_cache_sdk_objects(monkeypatch):
    from cytebase import _embeddings, _releases
    from cytebase.catalog import Catalog
    from cytebase.entry import DatasetEntry

    exports = {
        "Catalog": Catalog,
        "DatasetEntry": DatasetEntry,
        "embeddings": _embeddings.embeddings,
        "embedding": _embeddings.embedding,
        "embedding_coordinates": _embeddings.embedding_coordinates,
        "Release": _releases.Release,
        "releases": _releases.releases,
    }
    for name, value in exports.items():
        monkeypatch.delitem(vars(cytebase), name, raising=False)
        assert getattr(cytebase, name) is value
        assert vars(cytebase)[name] is value


def test_removed_dataset_wrapper_is_not_exported():
    from importlib.util import find_spec

    assert find_spec("cytebase.dataset") is None
    assert "CytebaseDataset" not in cytebase.__all__
    assert "CytebaseDataset" not in dir(cytebase)
    with pytest.raises(AttributeError, match="has no attribute 'CytebaseDataset'"):
        cytebase.CytebaseDataset


def test_unknown_module_attributes_raise():
    with pytest.raises(AttributeError, match="has no attribute 'missing'"):
        cytebase.missing


def test_dir_lists_lazy_exports():
    assert set(cytebase.__all__) <= set(dir(cytebase))
    assert {
        "Catalog",
        "DatasetEntry",
        "embeddings",
        "embedding",
        "embedding_coordinates",
        "Release",
        "releases",
    } == set(cytebase.__all__)


def test_example_downloads_stay_in_cytearc():
    """CyteArc's example-data repositories are ``cytearc.datasets``, not CyteBase."""
    for name in ("Repository", "connect", "list_repositories"):
        assert name not in dir(cytebase)
        with pytest.raises(AttributeError):
            getattr(cytebase, name)

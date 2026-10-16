"""Discover CyteBase datasets and connect to their CyteArc DataStores."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._embeddings import embedding as embedding
    from ._embeddings import embedding_coordinates as embedding_coordinates
    from ._embeddings import embeddings as embeddings
    from ._releases import Release as Release
    from ._releases import releases as releases
    from .catalog import Catalog as Catalog
    from .entry import DatasetEntry as DatasetEntry

__all__ = [
    "Catalog",
    "DatasetEntry",
    "Release",
    "embedding",
    "embedding_coordinates",
    "embeddings",
    "releases",
]


def __getattr__(name: str) -> Any:
    if name == "Catalog":
        from .catalog import Catalog

        globals()[name] = Catalog
        return Catalog
    if name == "DatasetEntry":
        from .entry import DatasetEntry

        globals()[name] = DatasetEntry
        return DatasetEntry
    if name in {"embedding", "embedding_coordinates", "embeddings"}:
        from . import _embeddings

        value = getattr(_embeddings, name)
        globals()[name] = value
        return value
    if name in {"Release", "releases"}:
        from . import _releases

        value = getattr(_releases, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

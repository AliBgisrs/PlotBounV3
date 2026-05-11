from __future__ import annotations

from typing import Optional

import rasterio
from rasterio.enums import Resampling


DEFAULT_FACTORS = [2, 4, 8, 16, 32, 64]


def has_overviews(path: str) -> bool:
    with rasterio.open(path) as ds:
        return bool(ds.overviews(1))


def needs_overviews(path: str, min_dim_threshold: int = 4000) -> bool:
    """True if the raster is large enough to benefit and doesn't already have overviews."""
    with rasterio.open(path) as ds:
        if max(ds.width, ds.height) < min_dim_threshold:
            return False
        return not bool(ds.overviews(1))


def build_overviews(
    path: str,
    factors: Optional[list[int]] = None,
    resampling: Resampling = Resampling.average,
    progress=None,
) -> None:
    """Build internal overviews. Modifies the source file in place (adds embedded pyramids).

    For files where in-place modification isn't possible (read-only media), this will raise.
    """
    factors = factors or DEFAULT_FACTORS
    with rasterio.open(path, "r+") as ds:
        ds.build_overviews(factors, resampling)
        ds.update_tags(ns="rio_overview", resampling=resampling.name)
    if progress is not None:
        progress(1.0)


def ensure_overviews(path: str, progress=None) -> bool:
    """Build overviews if missing and the raster is large. Returns True if built."""
    if not needs_overviews(path):
        return False
    build_overviews(path, progress=progress)
    return True

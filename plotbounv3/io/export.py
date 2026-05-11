from __future__ import annotations

import json
import os
from typing import Iterable, Optional

from ..grid import Plot


SUPPORTED_FORMATS = ["geojson", "shapefile", "geopackage", "gdb"]


def plots_to_geojson(plots: Iterable[Plot], crs: Optional[str] = None) -> dict:
    features = []
    for plot in plots:
        ring = [list(p) for p in plot.corners_geo]
        if ring and ring[0] != ring[-1]:
            ring.append(ring[0])
        features.append({
            "type": "Feature",
            "properties": {"ID": plot.id, "Trial": plot.trial},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })
    fc: dict = {"type": "FeatureCollection", "features": features}
    if crs:
        fc["crs"] = {"type": "name", "properties": {"name": crs}}
    return fc


def export_geojson(plots: Iterable[Plot], path: str, crs: Optional[str] = None) -> None:
    fc = plots_to_geojson(plots, crs=crs)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, indent=2)


def _fiona_write(plots, path, driver, crs, layer=None):
    import fiona
    plots = list(plots)
    schema = {
        "geometry": "Polygon",
        "properties": [("ID", "int"), ("Trial", "int")],
    }
    open_kwargs = dict(mode="w", driver=driver, schema=schema, crs=crs)
    if layer is not None:
        open_kwargs["layer"] = layer
    with fiona.open(path, **open_kwargs) as sink:
        for plot in plots:
            ring = [tuple(p) for p in plot.corners_geo]
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            sink.write({
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {"ID": int(plot.id), "Trial": int(plot.trial)},
            })


def export_shapefile(plots: Iterable[Plot], path: str, crs: Optional[str] = None) -> None:
    _fiona_write(plots, path, driver="ESRI Shapefile", crs=crs)


def export_geopackage(plots: Iterable[Plot], path: str, crs: Optional[str] = None, layer: str = "plots") -> None:
    _fiona_write(plots, path, driver="GPKG", crs=crs, layer=layer)


def export_gdb(plots: Iterable[Plot], path: str, crs: Optional[str] = None, layer: str = "plots") -> None:
    """Write to a File Geodatabase via the OpenFileGDB driver.

    Requires GDAL >= 3.6. Raises a clear error otherwise.
    """
    try:
        _fiona_write(plots, path, driver="OpenFileGDB", crs=crs, layer=layer)
    except Exception as e:
        raise RuntimeError(
            "GDB export failed. This requires GDAL >= 3.6 with OpenFileGDB write support. "
            f"Underlying error: {e}"
        ) from e


def export_by_format(
    plots: Iterable[Plot],
    path: str,
    fmt: str,
    crs: Optional[str] = None,
) -> None:
    fmt = fmt.lower()
    if fmt == "geojson":
        export_geojson(plots, path, crs=crs)
    elif fmt == "shapefile":
        export_shapefile(plots, path, crs=crs)
    elif fmt == "geopackage":
        export_geopackage(plots, path, crs=crs)
    elif fmt == "gdb":
        export_gdb(plots, path, crs=crs)
    else:
        raise ValueError(f"Unknown export format: {fmt}")

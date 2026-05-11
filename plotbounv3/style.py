from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlotStyle:
    polygon_color: str = "#FF0000"
    polygon_edited_color: str = "#FFFF00"
    label_color: str = "#FFFFFF"
    polygon_width: int = 2          # screen pixels (cosmetic pen)
    label_size_px: int = 12         # screen pixels (cosmetic font)
    origin_color: str = "#00FFFF"

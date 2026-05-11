from __future__ import annotations

from typing import Optional

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window


class RasterSource:
    """Wraps a rasterio dataset for fast windowed RGB reads at arbitrary resolution.

    Uses overviews when reading at a coarser scale, so reads stay constant-time
    regardless of full-image size.
    """

    def __init__(self, path: str):
        self.path = path
        self._ds = rasterio.open(path)
        self.width = self._ds.width
        self.height = self._ds.height
        self.count = self._ds.count
        self.dtype = self._ds.dtypes[0]
        self.crs = self._ds.crs
        self.transform = self._ds.transform
        self._display_bands = self._pick_display_bands(self.count)
        self._stretch: list[tuple[float, float]] = []
        self._compute_stretch()

    def close(self):
        try:
            self._ds.close()
        except Exception:
            pass

    def __del__(self):
        self.close()

    @staticmethod
    def _pick_display_bands(count: int) -> tuple[int, int, int]:
        if count == 1:
            return (1, 1, 1)
        if count == 2:
            return (1, 2, 1)
        # RGB (3), RGBA (4), or first three of multispectral
        return (1, 2, 3)

    def set_display_bands(self, bands: tuple[int, int, int]) -> None:
        self._display_bands = bands
        self._compute_stretch()

    def _compute_stretch(self) -> None:
        """Compute 2nd/98th percentile per display band from a downsampled read.

        This gives auto-contrast for uint16/float rasters without flicker across pans.
        """
        target_max = 1024
        factor = max(1, max(self.width, self.height) // target_max)
        out_h = max(1, self.height // factor)
        out_w = max(1, self.width // factor)
        try:
            arr = self._ds.read(
                list(self._display_bands),
                out_shape=(3, out_h, out_w),
                resampling=Resampling.average,
            )
        except Exception:
            arr = self._ds.read(
                list(self._display_bands),
                out_shape=(3, out_h, out_w),
            )
        self._stretch = []
        for i in range(3):
            band = arr[i]
            valid = band[np.isfinite(band)]
            if valid.size == 0:
                self._stretch.append((0.0, 255.0))
                continue
            lo = float(np.percentile(valid, 2))
            hi = float(np.percentile(valid, 98))
            if hi <= lo:
                hi = lo + 1.0
            self._stretch.append((lo, hi))

    def read_rgb_window(
        self,
        col_off: int,
        row_off: int,
        win_w: int,
        win_h: int,
        out_w: int,
        out_h: int,
    ) -> np.ndarray:
        """Read a window and return it as (out_h, out_w, 3) uint8 RGB.

        rasterio uses overviews automatically when out_shape is smaller than the window.
        """
        col_off = max(0, min(self.width - 1, int(col_off)))
        row_off = max(0, min(self.height - 1, int(row_off)))
        win_w = max(1, min(self.width - col_off, int(win_w)))
        win_h = max(1, min(self.height - row_off, int(win_h)))
        out_w = max(1, int(out_w))
        out_h = max(1, int(out_h))

        window = Window(col_off, row_off, win_w, win_h)
        try:
            arr = self._ds.read(
                list(self._display_bands),
                window=window,
                out_shape=(3, out_h, out_w),
                resampling=Resampling.bilinear,
                boundless=False,
            )
        except Exception:
            arr = self._ds.read(
                list(self._display_bands),
                window=window,
                out_shape=(3, out_h, out_w),
                boundless=False,
            )

        rgb = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        for i in range(3):
            lo, hi = self._stretch[i]
            v = arr[i].astype(np.float32, copy=False)
            v = (v - lo) * (255.0 / (hi - lo))
            np.clip(v, 0, 255, out=v)
            rgb[..., i] = v.astype(np.uint8)
        return rgb

    def pixel_to_geo(self, px: float, py: float) -> tuple[float, float]:
        x, y = self.transform * (px, py)
        return float(x), float(y)

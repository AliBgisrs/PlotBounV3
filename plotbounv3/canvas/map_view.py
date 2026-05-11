from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QRectF
from PySide6.QtGui import QImage, QPixmap, QTransform, QPainter, QPen, QColor, QWheelEvent, QMouseEvent
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem

from ..raster import RasterSource


class MapView(QGraphicsView):
    """QGraphicsView that renders a RasterSource via windowed reads.

    Scene coordinates equal image pixel coordinates. Pan/zoom triggers a debounced
    re-read of the visible window at the viewport's screen resolution.
    """

    origin_clicked = Signal(float, float)  # scene (image-pixel) coords

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._pixmap_item.setTransformationMode(Qt.SmoothTransformation)
        self._pixmap_item.setZValue(-1000)
        self._scene.addItem(self._pixmap_item)

        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setBackgroundBrush(QColor(20, 20, 20))

        self._source: Optional[RasterSource] = None
        self._origin_marker: Optional[QGraphicsItem] = None
        self._origin_locked: bool = False
        self._origin_color: str = "#00FFFF"
        self._origin_xy: Optional[tuple[float, float]] = None

        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(120)
        self._redraw_timer.timeout.connect(self._do_redraw)

    def set_source(self, source: Optional[RasterSource]) -> None:
        if self._source is not None:
            self._source.close()
        self._source = source
        if source is None:
            self._pixmap_item.setPixmap(QPixmap())
            self._scene.setSceneRect(QRectF(0, 0, 1, 1))
            return
        self._scene.setSceneRect(QRectF(0, 0, source.width, source.height))
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._schedule_redraw()

    def set_origin(self, x: float, y: float) -> None:
        self._origin_xy = (x, y)
        if self._origin_marker is not None:
            self._scene.removeItem(self._origin_marker)
            self._origin_marker = None
        if self._source is None:
            return
        size = max(8.0, min(self._source.width, self._source.height) / 200.0)
        from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsItemGroup
        group = QGraphicsItemGroup()
        pen = QPen(QColor(self._origin_color))
        pen.setWidth(2)
        pen.setCosmetic(True)
        h = QGraphicsLineItem(x - size, y, x + size, y)
        v = QGraphicsLineItem(x, y - size, x, y + size)
        for ln in (h, v):
            ln.setPen(pen)
            group.addToGroup(ln)
        group.setZValue(900)
        self._scene.addItem(group)
        self._origin_marker = group

    def set_origin_locked(self, locked: bool) -> None:
        self._origin_locked = locked

    def set_origin_color(self, color: str) -> None:
        self._origin_color = color
        if self._origin_xy is not None:
            x, y = self._origin_xy
            self.set_origin(x, y)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._source is None:
            return
        factor = 1.25 if event.angleDelta().y() > 0 else (1.0 / 1.25)
        self.scale(factor, factor)
        self._schedule_redraw()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._source is not None and not self._origin_locked:
            scene_pt = self.mapToScene(event.position().toPoint())
            x = scene_pt.x()
            y = scene_pt.y()
            if 0 <= x < self._source.width and 0 <= y < self._source.height:
                self.origin_clicked.emit(x, y)
                event.accept()
                return
        super().mousePressEvent(event)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self._schedule_redraw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_redraw()

    def _schedule_redraw(self) -> None:
        self._redraw_timer.start()

    def _do_redraw(self) -> None:
        if self._source is None:
            return
        vp = self.viewport()
        if vp.width() <= 0 or vp.height() <= 0:
            return

        visible_scene = self.mapToScene(vp.rect()).boundingRect()
        col_off = max(0, int(visible_scene.x()))
        row_off = max(0, int(visible_scene.y()))
        right = min(self._source.width, int(visible_scene.x() + visible_scene.width()) + 1)
        bottom = min(self._source.height, int(visible_scene.y() + visible_scene.height()) + 1)
        win_w = right - col_off
        win_h = bottom - row_off
        if win_w <= 0 or win_h <= 0:
            self._pixmap_item.setPixmap(QPixmap())
            return

        # Output resolution = viewport size, but never up-sample beyond the window.
        out_w = min(win_w, max(1, vp.width()))
        out_h = min(win_h, max(1, vp.height()))

        rgb = self._source.read_rgb_window(col_off, row_off, win_w, win_h, out_w, out_h)
        h, w, _ = rgb.shape
        # Copy bytes — the QImage must own its data, since the numpy array may be freed.
        img = QImage(bytes(rgb.data), w, h, w * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        self._pixmap_item.setPixmap(pixmap)
        self._pixmap_item.setPos(col_off, row_off)
        self._pixmap_item.setTransform(QTransform.fromScale(win_w / w, win_h / h))

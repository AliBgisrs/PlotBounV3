from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QColor, QBrush, QFont, QPolygonF, QTransform
from PySide6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsPolygonItem,
    QGraphicsSimpleTextItem,
    QGraphicsScene,
    QGraphicsItem,
)

from ..grid import Plot
from ..style import PlotStyle


class PlotLayer:
    """Manages polygon + label items on the scene.

    Pens are cosmetic (width in screen pixels), and labels use
    ItemIgnoresTransformations so font size stays constant in screen pixels
    regardless of zoom level.
    """

    def __init__(self, scene: QGraphicsScene):
        self._scene = scene
        self._group: QGraphicsItemGroup | None = None
        self._style = PlotStyle()
        self._plots: list[Plot] = []

    def set_style(self, style: PlotStyle) -> None:
        self._style = style
        if self._plots:
            self.render(self._plots)

    def clear(self) -> None:
        if self._group is not None:
            self._scene.removeItem(self._group)
            self._group = None
        self._plots = []

    def render(self, plots: Iterable[Plot]) -> None:
        if self._group is not None:
            self._scene.removeItem(self._group)
            self._group = None
        self._plots = list(plots)

        group = QGraphicsItemGroup()
        group.setZValue(500)

        normal_pen = QPen(QColor(self._style.polygon_color))
        normal_pen.setCosmetic(True)
        normal_pen.setWidth(self._style.polygon_width)
        edit_pen = QPen(QColor(self._style.polygon_edited_color))
        edit_pen.setCosmetic(True)
        edit_pen.setWidth(self._style.polygon_width)

        font = QFont()
        font.setPointSize(self._style.label_size_px)
        font.setBold(True)
        text_brush = QBrush(QColor(self._style.label_color))

        for plot in self._plots:
            poly = QPolygonF([QPointF(p[0], p[1]) for p in plot.corners_px])
            item = QGraphicsPolygonItem(poly)
            item.setPen(edit_pen if plot.is_edited else normal_pen)
            item.setBrush(Qt.NoBrush)
            group.addToGroup(item)

            label = QGraphicsSimpleTextItem(str(plot.id))
            label.setFont(font)
            label.setBrush(text_brush)
            label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            cx, cy = plot.center_px
            label.setPos(cx, cy)
            br = label.boundingRect()
            label.setTransform(QTransform().translate(-br.width() / 2.0, -br.height() / 2.0))
            group.addToGroup(label)

        self._scene.addItem(group)
        self._group = group

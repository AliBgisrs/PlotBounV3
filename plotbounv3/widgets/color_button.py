from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton, QColorDialog


class ColorButton(QPushButton):
    color_changed = Signal(str)

    def __init__(self, color: str = "#FF0000", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(48, 22)
        self.setCursor(self.cursor())
        self._refresh()
        self.clicked.connect(self._pick)

    def color(self) -> str:
        return self._color.name()

    def setColorName(self, name: str) -> None:
        c = QColor(name)
        if c.isValid():
            self._color = c
            self._refresh()
            self.color_changed.emit(self._color.name())

    def _refresh(self) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color.name()}; "
            f"border: 1px solid #555; border-radius: 3px; }}"
        )

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(self._color, self, "Choose color")
        if chosen.isValid() and chosen.name() != self._color.name():
            self._color = chosen
            self._refresh()
            self.color_changed.emit(self._color.name())

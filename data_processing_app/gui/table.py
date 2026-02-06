from PySide6.QtWidgets import (QAbstractItemView, QTableView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDrag, QCursor, QPainter, QColor

class DragDropTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        
        self.preview_indexes = []

    def startDrag(self, supportedActions):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        mouse_index = self.indexAt(self.mapFromGlobal(QCursor.pos()))
        if mouse_index in indexes:
            drag = QDrag(self)
            mime = self.model().mimeData(indexes)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)

    def dragMoveEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            self.clear_preview()
            return
        model = self.model()
        selected = self.selectedIndexes()
        if not selected:
            self.clear_preview()
            return
        rows = sorted(set(i.row() for i in selected))
        cols = sorted(set(i.column() for i in selected))
        top_left_row = index.row()
        top_left_col = index.column()
        self.preview_indexes = [
            model.index(top_left_row + r_i, top_left_col + c_i)
            for r_i, r in enumerate(rows)
            for c_i, c in enumerate(cols)
            if (top_left_row + r_i < model.rowCount() and top_left_col + c_i < model.columnCount())]
        self.viewport().update()
        event.accept()

    def clear_preview(self):
        if self.preview_indexes:
            self.preview_indexes = []
            self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.preview_indexes:
            return
        painter = QPainter(self.viewport())
        painter.setBrush(QColor(0, 120, 215, 50))
        painter.setPen(QColor(0, 120, 215))
        for idx in self.preview_indexes:
            rect = self.visualRect(idx)
            painter.drawRect(rect)

    def dragLeaveEvent(self, event):
        self.clear_preview()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        if not index.isValid():
            event.ignore()
            return
        model = self.model()
        if not model:
            event.ignore()
            return
        if event.mimeData().hasFormat(model.MIME_TYPE):
            if model.dropMimeData(event.mimeData(), Qt.DropAction.MoveAction, index.row(), index.column(), index):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
        self.clear_preview()
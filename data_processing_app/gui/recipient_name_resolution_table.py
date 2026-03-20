from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView,QHeaderView,QTableWidget,QTableWidgetItem

EDITABLE_COLUMNS = {"Recipient Name"}

def _make_item(text: str, *, editable: bool) -> QTableWidgetItem:
    item = QTableWidgetItem("" if text is None else str(text))
    flags = item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
    if editable:
        flags |= Qt.ItemFlag.ItemIsEditable
    else:
        flags &= ~Qt.ItemFlag.ItemIsEditable
    item.setFlags(flags)
    return item

class RecipientNameResolutionTable(QTableWidget):
    HEADERS = ["Recipient Name","Company","PAF Address 1","PAF Town","Reject Reason"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)

        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed | QAbstractItemView.EditTrigger.AnyKeyPressed)

        self.verticalHeader().setVisible(False)

        hdr = self.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(True)

    def set_rows(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        self.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, header in enumerate(self.HEADERS):
                value = row.get(header, "")
                editable = header in EDITABLE_COLUMNS
                self.setItem(r, c, _make_item(value, editable=editable))

        try:
            self.resizeColumnsToContents()
            self.resizeRowsToContents()
        except Exception:
            pass

    def rows(self) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for r in range(self.rowCount()):
            row: dict[str, str] = {}
            for c, header in enumerate(self.HEADERS):
                item = self.item(r, c)
                row[header] = "" if item is None else item.text().strip()
            out.append(row)
        return out

    def selected_row_indices(self) -> list[int]:
        model = self.selectionModel()
        if model is None:
            return []
        return sorted({index.row() for index in model.selectedRows()})
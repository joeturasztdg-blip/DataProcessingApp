from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from gui.recipient_name_resolution_table import RecipientNameResolutionTable


class RecipientNameResolutionDialog(QDialog):
    def __init__(self, rows, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Resolve Recipient Names")
        self.resize(900, 500)

        self._rows = [dict(r or {}) for r in rows]
        self._removed: set[int] = set()

        layout = QVBoxLayout(self)

        self.count_label = QLabel(f"Rows requiring review: {len(self._rows)}")
        layout.addWidget(self.count_label)

        self.table = RecipientNameResolutionTable()
        self.table.set_rows(self._rows)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()

        self.btn_remove = QPushButton("Remove Selected")
        btn_row.addWidget(self.btn_remove)

        btn_row.addStretch()

        self.btn_update = QPushButton("Update")
        btn_row.addWidget(self.btn_update)

        self.btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(self.btn_cancel)

        layout.addLayout(btn_row)

        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_update.clicked.connect(self.accept)

    def _remove_selected(self) -> None:
        selected = self.table.selected_row_indices()
        if not selected:
            return

        self._removed.update(selected)

        kept_rows = [
            row for i, row in enumerate(self.table.rows())
            if i not in self._removed
        ]
        self.table.set_rows(kept_rows)
        self.count_label.setText(f"Rows requiring review: {len(kept_rows)}")

        if not kept_rows:
            self.accept()

    def result_rows(self) -> list[dict[str, str]]:
        return self.table.rows()

    def removed_indices(self) -> set[int]:
        return set(self._removed)
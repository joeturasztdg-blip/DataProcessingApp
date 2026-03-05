from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget,
    QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox
)
from PySide6.QtWidgets import QHeaderView
from PySide6.QtCore import Qt

from workspace.base import BaseWorkflow
from processing.repos.login_repo import LoginRepository
from processing.repos.seeds_repo import SeedsRepository


class QueryDatabases(BaseWorkflow):
    def run(self, checked: bool = False):
        dlg = _QueryDatabasesDialog(self.mw)
        dlg.exec()


class _QueryDatabasesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query logins and seeds")

        root = QVBoxLayout(self)

        tabs = QTabWidget()
        root.addWidget(tabs)

        mailmark_repo = LoginRepository(db_filename="mailmark_logins.db", table_name="mailmark_logins")
        mixed_repo = LoginRepository(db_filename="mixed_weight_logins.db", table_name="mixed_weight_logins")
        seeds_repo = SeedsRepository()

        tabs.addTab(_LoginBrowserTab(repo=mailmark_repo, parent=self), "Mailmark logins")
        tabs.addTab(_LoginBrowserTab(repo=mixed_repo, parent=self), "Mixed weight logins")
        tabs.addTab(_SeedsBrowserTab(repo=seeds_repo, parent=self), "Seeds")

        tabs.setCurrentIndex(0)
        self.resize(1040, 720)


# ---------------- shared helpers ----------------

def _make_readonly_item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return it

def _make_editable_item(text: str) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
    return it

def _get_cell_text(table: QTableWidget, r: int, c: int) -> str:
    it = table.item(r, c)
    return (it.text() if it else "").strip()


class _LoginBrowserTab(QWidget):
    def __init__(self, *, repo: LoginRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._new_row_indices: list[int] = []
        root = QVBoxLayout(self)
        # Filter bar
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Filter:"))

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Search name/username...")
        bar.addWidget(self.edit, 1)

        self.btn_go = QPushButton("Go")
        self.btn_clear = QPushButton("Clear")
        bar.addWidget(self.btn_go)
        bar.addWidget(self.btn_clear)
        root.addLayout(bar)

        self.lbl_status = QLabel("")
        root.addWidget(self.lbl_status)
        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Username", "Password"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(True)

        root.addWidget(self.table, 1)
        # Bottom buttons
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_add = QPushButton("Add row")
        self.btn_exec = QPushButton("Execute")
        bottom.addWidget(self.btn_add)
        bottom.addWidget(self.btn_exec)
        root.addLayout(bottom)
        # Wiring
        self.btn_go.clicked.connect(self._apply_filter)
        self.btn_clear.clicked.connect(self._clear_filter)
        self.edit.returnPressed.connect(self._apply_filter)

        self.btn_add.clicked.connect(self._add_row)
        self.btn_exec.clicked.connect(self._execute_inserts)

        self._load_all()

    def _set_rows(self, rows: list[dict]):
        self._new_row_indices.clear()

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(rows))

            for r_i, row in enumerate(rows):
                id_item = QTableWidgetItem()
                id_item.setData(Qt.ItemDataRole.DisplayRole, int(row.get("ID", 0)))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r_i, 0, id_item)

                self.table.setItem(r_i, 1, _make_readonly_item(str(row.get("Name", "") or "")))
                self.table.setItem(r_i, 2, _make_readonly_item(str(row.get("Username", "") or "")))
                self.table.setItem(r_i, 3, _make_readonly_item(str(row.get("Password", "") or "")))

            self.lbl_status.setText(f"Rows: {len(rows)}")
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.table.resizeColumnsToContents()

    def _load_all(self):
        try:
            rows = self.repo.list_all()
            self._set_rows(rows)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        except Exception as e:
            QMessageBox.critical(self, "Query logins", str(e))

    def _apply_filter(self):
        q = (self.edit.text() or "").strip()
        try:
            rows = self.repo.search(q)
            self._set_rows(rows)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        except Exception as e:
            QMessageBox.critical(self, "Query logins", str(e))

    def _clear_filter(self):
        self.edit.setText("")
        self._load_all()

    def _add_row(self):
        try:
            next_id = self.repo.next_id()
        except Exception as e:
            QMessageBox.critical(self, "Add row", f"Could not determine next ID:\n{e}")
            return
        self.table.setSortingEnabled(False)

        r = self.table.rowCount()
        self.table.insertRow(r)

        id_item = QTableWidgetItem()
        id_item.setData(Qt.ItemDataRole.DisplayRole, int(next_id))
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, id_item)
        # editable cells for user input
        self.table.setItem(r, 1, _make_editable_item(""))
        self.table.setItem(r, 2, _make_editable_item(""))
        self.table.setItem(r, 3, _make_editable_item(""))

        self._new_row_indices.append(r)
        self.table.resizeColumnsToContents()
        # focus first editable cell
        self.table.setCurrentCell(r, 1)
        self.table.editItem(self.table.item(r, 1))

    def _execute_inserts(self):
        if not self._new_row_indices:
            QMessageBox.information(self, "Execute", "No new rows to insert.")
            return
        payloads = []
        for r in list(self._new_row_indices):
            id_val = self.table.item(r, 0).data(Qt.ItemDataRole.DisplayRole)
            try:
                id_int = int(id_val)
            except Exception:
                QMessageBox.critical(self, "Execute", f"Row {r+1}: invalid ID.")
                return

            name = _get_cell_text(self.table, r, 1)
            username = _get_cell_text(self.table, r, 2)
            password = _get_cell_text(self.table, r, 3)

            payloads.append((r, id_int, name, username, password))
            
        try:
            with self.repo._connect() as con:
                cur = con.cursor()
                for (r, id_int, name, username, password) in payloads:
                    cur.execute(
                        f"INSERT INTO {self.repo.table_name} (ID, Name, Username, Password) VALUES (?, ?, ?, ?)",
                        (id_int, name, username, password))
                con.commit()

        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Execute", f"DB constraint error:\n{e}")
            return
        except Exception as e:
            QMessageBox.critical(self, "Execute", f"Insert failed:\n{e}")
            return

        QMessageBox.information(self, "Execute", f"Inserted {len(payloads)} row(s).")
        self._load_all()

class _SeedsBrowserTab(QWidget):
    def __init__(self, *, repo: SeedsRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._new_row_indices: list[int] = []

        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Filter:"))

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Search key/category/name...")
        bar.addWidget(self.edit, 1)

        self.btn_go = QPushButton("Go")
        self.btn_clear = QPushButton("Clear")
        bar.addWidget(self.btn_go)
        bar.addWidget(self.btn_clear)
        root.addLayout(bar)

        self.lbl_status = QLabel("")
        root.addWidget(self.lbl_status)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["ID", "KEY", "Category", "Name", "Address 1", "Address 2", "Town", "Postcode", "DPS"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(False)

        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_add = QPushButton("Add row")
        self.btn_exec = QPushButton("Execute")
        bottom.addWidget(self.btn_add)
        bottom.addWidget(self.btn_exec)
        root.addLayout(bottom)

        self.btn_go.clicked.connect(self._apply_filter)
        self.btn_clear.clicked.connect(self._clear_filter)
        self.edit.returnPressed.connect(self._apply_filter)

        self.btn_add.clicked.connect(self._add_row)
        self.btn_exec.clicked.connect(self._execute_inserts)

        self._load_all()

    def _set_rows(self, rows: list[dict]):
        self._new_row_indices.clear()

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(rows))

            for r_i, row in enumerate(rows):
                id_item = QTableWidgetItem()
                id_item.setData(Qt.ItemDataRole.DisplayRole, int(row.get("ID", 0)))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r_i, 0, id_item)
                # existing rows read-only
                self.table.setItem(r_i, 1, _make_readonly_item(str(row.get("KEY", "") or "")))
                self.table.setItem(r_i, 2, _make_readonly_item(str(row.get("Category", "") or "")))
                self.table.setItem(r_i, 3, _make_readonly_item(str(row.get("Name", "") or "")))
                self.table.setItem(r_i, 4, _make_readonly_item(str(row.get("Address_1", "") or "")))
                self.table.setItem(r_i, 5, _make_readonly_item(str(row.get("Address_2", "") or "")))
                self.table.setItem(r_i, 6, _make_readonly_item(str(row.get("Town", "") or "")))
                self.table.setItem(r_i, 7, _make_readonly_item(str(row.get("Postcode", "") or "")))
                self.table.setItem(r_i, 8, _make_readonly_item(str(row.get("DPS", "") or "")))

            self.lbl_status.setText(f"Rows: {len(rows)}")
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

        self.table.resizeColumnsToContents()

    def _load_all(self):
        try:
            rows = self.repo.list_all_rows()
            self._set_rows(rows)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        except Exception as e:
            QMessageBox.critical(self, "Query seeds", str(e))

    def _apply_filter(self):
        q = (self.edit.text() or "").strip()
        try:
            rows = self.repo.search_rows(q)
            self._set_rows(rows)
            self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        except Exception as e:
            QMessageBox.critical(self, "Query seeds", str(e))

    def _clear_filter(self):
        self.edit.setText("")
        self._load_all()

    def _add_row(self):
        try:
            next_id = self.repo.next_id()
        except Exception as e:
            QMessageBox.critical(self, "Add row", f"Could not determine next ID:\n{e}")
            return

        self.table.setSortingEnabled(False)

        r = self.table.rowCount()
        self.table.insertRow(r)

        id_item = QTableWidgetItem()
        id_item.setData(Qt.ItemDataRole.DisplayRole, int(next_id))
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, id_item)
        # editable cells for user input
        for c in range(1, 9):
            self.table.setItem(r, c, _make_editable_item(""))

        self._new_row_indices.append(r)
        self.table.resizeColumnsToContents()

        self.table.setCurrentCell(r, 1)
        self.table.editItem(self.table.item(r, 1))

    def _execute_inserts(self):
        if not self._new_row_indices:
            QMessageBox.information(self, "Execute", "No new rows to insert.")
            return
        payloads = []
        for r in list(self._new_row_indices):
            id_val = self.table.item(r, 0).data(Qt.ItemDataRole.DisplayRole)
            try:
                id_int = int(id_val)
            except Exception:
                QMessageBox.critical(self, "Execute", f"Row {r+1}: invalid ID.")
                return

            key = _get_cell_text(self.table, r, 1)
            category = _get_cell_text(self.table, r, 2)
            name = _get_cell_text(self.table, r, 3)
            address_1 = _get_cell_text(self.table, r, 4)
            address_2 = _get_cell_text(self.table, r, 5)
            town = _get_cell_text(self.table, r, 6)
            postcode = _get_cell_text(self.table, r, 7)
            dps = _get_cell_text(self.table, r, 8)

            payloads.append((id_int, key, category, name, address_1, address_2, town, postcode, dps))

        try:
            with self.repo._connect() as con:
                cur = con.cursor()
                for (id_int, key, category, name, address_1, address_2, town, postcode, dps) in payloads:
                    cur.execute(
                        "INSERT INTO Seeds (ID, KEY, Category, Name, Address_1, Address_2, Town, Postcode, DPS) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (id_int, key, category, name, address_1, address_2, town, postcode, dps))
                con.commit()

        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, "Execute", f"DB constraint error:\n{e}")
            return
        except Exception as e:
            QMessageBox.critical(self, "Execute", f"Insert failed:\n{e}")
            return

        QMessageBox.information(self, "Execute", f"Inserted {len(payloads)} row(s).")
        self._load_all()
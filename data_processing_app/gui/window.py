import os
import stat

from config.constants import APP_TITLE

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QMessageBox, QLabel, QFileDialog, QGroupBox, QTextEdit)
from PySide6.QtCore import Qt, Signal

from workspace.services import build_services
from workspace.jobs import JobRunner

from workspace.change_delim import ChangeDelimiter
from workspace.create_file import CreateFile
from workspace.split_file import SplitFile
from workspace.update_out_file import UpdateOutFile
from workspace.create_zip import CreateZip
from workspace.generate_password import GeneratePassword
from workspace.print_pdf import PrintPdf

class MainWindow(QWidget):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(760, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel("<h2>Data processing application.</h2>")
        header.setAlignment(Qt.AlignCenter)
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)

        group = QGroupBox("Processing Actions")
        group_layout = QVBoxLayout(group)
        layout.addWidget(group)

        # ---- Log ----
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        self.log_signal.connect(self.log.append)

        # ---- Services + Jobs ----
        self.services = build_services(self)
        self.s = build_services(self)
        self.jobs = JobRunner(self)
        # ---- Workflows ----
        self.change_delim = ChangeDelimiter(self)
        self.create_file = CreateFile(self)
        self.split_file = SplitFile(self)
        self.update_out_file = UpdateOutFile(self)
        self.create_zip = CreateZip(self)
        self.generate_password = GeneratePassword(self)
        self.print_pdf = PrintPdf(self)

        # ---- Actions (buttons + wiring) ----
        actions = [
            ("btn_change_delim", "Change CSV Delimiter", self.change_delim.run),
            ("btn_create_file", "Create file", self.create_file.run),
            ("btn_split_file", "Split file", self.split_file.run),
            ("btn_update_out_file", "Update .OUT file", self.update_out_file.run),
            ("btn_create_zip", "Create ZIP", self.create_zip.run),
            ("btn_generate_random_password", "Generate Random Password", self.generate_password.run),
            ("btn_print_pdf", "Print PDF", self.print_pdf.run),
        ]

        for attr, text, slot in actions:
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.clicked.connect(slot)
            setattr(self, attr, btn)
            group_layout.addWidget(btn)

        self.last_input_dir = os.getcwd()

    # ---------------- UI helpers ----------------
    def show_error(self, title, text):
        QMessageBox.critical(self, title, text)
        self.s.logger.log(f"[ERROR] {title}: {text}", "red")

    def _get_start_dir(self, path=None):
        if path and os.path.exists(path):
            return path
        return self.last_input_dir or os.getcwd()

    def update_last_input_dir(self, selected_path):
        if not selected_path:
            return
        if isinstance(selected_path, (list, tuple)):
            selected_path = selected_path[0]
        if os.path.isfile(selected_path):
            self.last_input_dir = os.path.dirname(selected_path)
        elif os.path.isdir(selected_path):
            self.last_input_dir = selected_path

    def ask_open_file(self, title="Open file", filter="All Files (*)"):
        path, _ = QFileDialog.getOpenFileName(self, title, self._get_start_dir(), filter)
        if path:
            self.update_last_input_dir(path)
        return path or None

    def ask_open_files(self, title="Open files", filter="All Files (*)"):
        paths, _ = QFileDialog.getOpenFileNames(self, title, self._get_start_dir(), filter)
        if paths:
            self.update_last_input_dir(paths)
        return paths or None

    def ask_save_csv(self, title="Save file", filter="CSV Files (*.csv);;All Files (*)", defaultName=None):
        start_dir = self._get_start_dir()
        start_path = os.path.join(start_dir, defaultName) if defaultName else start_dir
        path, _ = QFileDialog.getSaveFileName(self, title, start_path, filter)
        if path:
            self.update_last_input_dir(path)
        return path or None

    def make_file_writable(self, path: str):
        if os.path.exists(path):
            attrs = os.stat(path).st_mode
            if not (attrs & stat.S_IWRITE):
                os.chmod(path, attrs | stat.S_IWRITE)

    def _save_csv(self, df, filename, has_header=True, delimiter=","):
        df.to_csv(filename, index=False, header=has_header, sep=delimiter)

    def _run_busy(self, title: str, message: str, fn, on_done=None, on_err=None, cancelable: bool = False):
        return self.jobs.run(title, message, fn, on_done=on_done, on_err=on_err, cancelable=cancelable)
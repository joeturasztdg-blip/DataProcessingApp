import os
import sys
import tempfile
import subprocess, platform, math
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QListWidget,
    QLabel, QDialog,)
import fitz

from config.constants import SYSTEM_PRINTERS


def maybe_append_label_page(input_pdf, enabled: bool):
    if not enabled:
        return input_pdf

    base = os.path.splitext(os.path.basename(input_pdf))[0]
    label_text = base.split("-", 1)[0]

    src = fitz.open(input_pdf)
    fd, temp_out = tempfile.mkstemp(suffix="_withlabel.pdf")
    os.close(fd)

    out = fitz.open()
    out.insert_pdf(src)

    LABEL_WIDTH  = 288   # 4"
    LABEL_HEIGHT = 432   # 6"

    page = out.new_page(width=LABEL_WIDTH, height=LABEL_HEIGHT)
    rect = fitz.Rect(0, 0, LABEL_WIDTH, LABEL_HEIGHT)

    page.insert_textbox(
        rect,
        label_text,
        fontsize=24,
        fontname="helv",
        color=(0, 0, 0),
        align=fitz.TEXT_ALIGN_CENTER,
        rotate=90
    )

    out.save(temp_out)
    out.close()
    src.close()

    return temp_out


def print_to_specific_printer(pdf_path, printer_name):
    system = platform.system()

    if system == "Windows":
        possible = []

        # ---- PyInstaller onefile bundle dir ----
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            possible.append(os.path.join(bundle, "SumatraPDF.exe"))

        # ---- Normal locations ----
        possible.extend([
            os.path.join(os.getcwd(), "SumatraPDF.exe"),
            os.path.join(os.path.dirname(sys.argv[0]), "SumatraPDF.exe"),
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
        ])

        sumatra = next((p for p in possible if os.path.exists(p)), None)
        if not sumatra:
            QMessageBox.critical(
                None,
                "Error",
                "SumatraPDF.exe not found.\nPlace it next to the application.",
            )
            return

        cmd = [
            sumatra,
            "-print-to", printer_name,
            "-print-settings", "noscale",
            "-silent",
            pdf_path,
        ]

        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return

    subprocess.run(["lp", "-d", printer_name, pdf_path])


class BatchPdfPrintDialog(QDialog):
    def __init__(self, pdf_list, print_opts, parent=None):
        super().__init__(parent)

        self.pdf_list = pdf_list
        self.print_opts = print_opts
        self.batch_index = 0
        self.batch_size = len(SYSTEM_PRINTERS)  # ← dynamic batch size

        self.setWindowTitle("Print Files")
        self.resize(300, 250)

        self.layout = QVBoxLayout(self)

        self.lbl_header = QLabel("Files Loaded:")
        self.layout.addWidget(self.lbl_header)

        self.file_list_widget = QListWidget()
        self.layout.addWidget(self.file_list_widget)

        total_batches = math.ceil(len(pdf_list) / self.batch_size)
        self.lbl_status = QLabel(f"Batch 1 / {total_batches}")
        self.layout.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_skip = QPushButton("Skip")
        self.btn_next = QPushButton("Print && Next")
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_skip)
        btn_row.addWidget(self.btn_next)
        self.layout.addLayout(btn_row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_skip.clicked.connect(self.handle_skip)
        self.btn_next.clicked.connect(self.handle_print_next)

        self.refresh_file_list()
        self.update_button_label()

    def refresh_file_list(self):
        self.file_list_widget.clear()
        batch = self.pdf_list[self.batch_index:self.batch_index + self.batch_size]
        for f in batch:
            self.file_list_widget.addItem(os.path.basename(f))

    def update_button_label(self):
        remaining = len(self.pdf_list) - self.batch_index
        if remaining <= self.batch_size:
            self.btn_next.setText("Print && Finish")
        else:
            self.btn_next.setText("Print && Next")

    def handle_print_next(self):
        batch_files = self.pdf_list[
            self.batch_index : self.batch_index + self.batch_size]

        for i, pdf in enumerate(batch_files):
            if i >= len(SYSTEM_PRINTERS):
                break
            final_pdf = maybe_append_label_page(
                pdf,
                self.print_opts.get("print_filename_label", True))
            print_to_specific_printer(final_pdf, SYSTEM_PRINTERS[i])


        self.batch_index += self.batch_size

        if self.batch_index >= len(self.pdf_list):
            self.lbl_status.setText("Finished")
            self.accept()
            return

        self.refresh_file_list()
        total_batches = math.ceil(len(self.pdf_list) / self.batch_size)
        current_batch = math.ceil(self.batch_index / self.batch_size) + 1
        self.lbl_status.setText(f"Batch {current_batch} / {total_batches}")
        self.update_button_label()

    def handle_skip(self):
        self.batch_index += self.batch_size

        if self.batch_index >= len(self.pdf_list):
            self.accept()
            return

        self.refresh_file_list()
        total_batches = math.ceil(len(self.pdf_list) / self.batch_size)
        current_batch = math.ceil(self.batch_index / self.batch_size) + 1
        self.lbl_status.setText(f"Batch {current_batch} / {total_batches}")
        self.update_button_label()
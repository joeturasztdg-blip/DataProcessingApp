from PySide6.QtWidgets import QDialog

from config.schemas import PRINT_PDF_SCHEMA
from gui.dialogs import OptionsDialog
from utils.pdf_utils import BatchPdfPrintDialog


class PrintPdf:
    def __init__(self, mw):
        self.mw = mw

    def run(self, checked: bool = False):
        pdfs = self.mw.ask_open_files("Select PDFs for batch print", "PDF Files (*.pdf)")
        if not pdfs:
            return

        dlg_opts = OptionsDialog(PRINT_PDF_SCHEMA, parent=self.mw, title="Print Options")
        if dlg_opts.exec() != QDialog.Accepted:
            return

        print_opts = dlg_opts.get_results()
        dlg = BatchPdfPrintDialog(pdfs, print_opts, self.mw)
        dlg.exec()

import os
from PySide6.QtWidgets import QDialog, QMessageBox

from config.schemas import CHANGE_DELIM_SCHEMA
from gui.dialogs import OptionsDialog


class ChangeDelimiter:
    """
    Workflow:
      - ask for input CSV/TXT
      - load via FileLoader
      - ask for output delimiter
      - ask for output path
      - save
    """

    def __init__(self, mw):
        self.mw = mw  # MainWindow (UI context)

    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose CSV/TXT file to load",
            "CSV/TXT Files (*.csv *.txt);;All Files (*)",
        )
        if not infile:
            return

        self.mw.make_file_writable(infile)

        def job_load():
            return self.mw.s.loader.load_file(infile)

        def on_err(err_text: str):
            self.mw.show_error("Change delimiter failed", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return

                dlg = OptionsDialog(CHANGE_DELIM_SCHEMA, parent=self.mw, title="Change CSV Delimiter")
                if dlg.exec() != QDialog.Accepted:
                    return

                out_delim = dlg.get_results().get("delimiter")
                if not out_delim:
                    return

                base = os.path.splitext(os.path.basename(infile))[0]
                default_name = f"{base}.csv"
                outfile = self.mw.ask_save_csv(
                    "Save CSV as",
                    "CSV Files (*.csv);;All Files (*)",
                    defaultName=default_name,
                )
                if not outfile:
                    return

                def job_save():
                    self.mw._save_csv(df, outfile, has_header=has_header, delimiter=out_delim)
                    return True

                self.mw._run_busy(
                    "Change CSV Delimiter",
                    "Saving file…",
                    job_save,
                    on_done=lambda _: self.mw.s.logger.log("File created successfully.", "green"),
                    on_err=lambda e: QMessageBox.critical(self.mw, "Save Error", e),
                )

            except Exception as e:
                self.mw.show_error("Change delimiter failed", str(e))

        self.mw._run_busy("Change CSV Delimiter", "Loading file…", job_load, on_done=on_loaded, on_err=on_err)
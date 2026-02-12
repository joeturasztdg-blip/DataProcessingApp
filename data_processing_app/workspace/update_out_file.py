import os
from PySide6.QtWidgets import QDialog, QMessageBox

from config.schemas import UPDATE_OUT_FILE_SCHEMA
from gui.dialogs import OptionsDialog


class UpdateOutFile:
    def __init__(self, mw):
        self.mw = mw

    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose CSV/TXT to update",
            "CSV/TXT/(*.OUT.csv *.OUT.txt);;All Files (*)",
        )
        if not infile:
            return

        self.mw.make_file_writable(infile)

        def job_load():
            return self.mw.s.loader.load_file(infile)

        def on_err(err_text: str):
            self.mw.show_error("Update OUT file failed", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return

                dlg = OptionsDialog(UPDATE_OUT_FILE_SCHEMA, parent=self.mw, title="Update Out File")
                if dlg.exec() != QDialog.Accepted:
                    return
                opts = dlg.get_results()

                # ---- UCID updates ----
                ucid_opts = opts.get("ucid_updates", {})
                ucid_mode = ucid_opts.get("value", "none")

                ucid_map = {}
                if ucid_mode == "1":
                    ucid1 = (ucid_opts.get("ucid1") or "").strip()
                    if ucid1:
                        ucid_map["UCID1"] = ucid1
                        ucid_map["UCID2"] = ucid1
                elif ucid_mode == "2":
                    ucid1 = (ucid_opts.get("ucid1") or "").strip()
                    ucid2 = (ucid_opts.get("ucid2") or "").strip()
                    if ucid1:
                        ucid_map["UCID1"] = ucid1
                    if ucid2:
                        ucid_map["UCID2"] = ucid2

                if ucid_map:
                    df = self.mw.s.transforms.update_UCID(df, ucid_map)

                # ---- Barcode padding ----
                padding_choice = opts.get("barcode_padding", "none")
                if padding_choice != "none":
                    df = self.mw.s.transforms.apply_barcode_padding(df, padding_choice)

                base = os.path.splitext(os.path.basename(infile))[0]
                default_name = f"{base}.csv"
                outfile = self.mw.ask_save_csv(
                    "Save OUT file CSV",
                    "CSV Files (*.csv);;All Files (*)",
                    defaultName=default_name,
                )
                if not outfile:
                    return

                delimiter = opts.get("delimiter", ",")

                def job_save():
                    self.mw._save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
                    return True

                self.mw._run_busy(
                    "Update OUT File",
                    "Saving file…",
                    job_save,
                    on_done=lambda _: self.mw.s.logger.log("OUT file updated successfully.", "green"),
                    on_err=lambda e: QMessageBox.critical(self.mw, "Save Error", e),
                )

            except Exception as e:
                self.mw.show_error("Update OUT file failed", str(e))

        self.mw._run_busy("Update OUT File", "Loading file…", job_load, on_done=on_loaded, on_err=on_err)

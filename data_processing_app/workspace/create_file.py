import os
from PySide6.QtWidgets import QDialog, QMessageBox

from config.schemas import CREATE_FILE_SCHEMA
from config.seeds import seed_dict
from gui.dialogs import OptionsDialog, PreviewDialog


class CreateFile:
    def __init__(self, mw):
        self.mw = mw  # MainWindow context

    def run(self, checked: bool = False):  # clicked(bool) safety
        infile = self.mw.ask_open_file(
            "Choose File",
            "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)",
        )
        if not infile:
            return

        dlg = OptionsDialog(CREATE_FILE_SCHEMA, parent=self.mw, title="Create File Options")
        if dlg.exec() != QDialog.Accepted:
            return

        opts = dlg.get_results()
        header_mode = opts.get("header_cleaning", "none")

        def job_load():
            return self.mw.s.loader.load_file(infile, header_cleaning_mode=header_mode)

        def on_err(err_text: str):
            QMessageBox.critical(self.mw, "Error", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return

                # -------------------- MMI --------------------
                mmi_opts = opts.get("mmi", {})
                if mmi_opts.get("enabled"):
                    mmi_type = mmi_opts.get("value")
                    try:
                        if mmi_type == "Scotts":
                            cell_name = (mmi_opts.get("cell_name") or "").strip()
                            if not cell_name:
                                QMessageBox.warning(
                                    self.mw,
                                    "Missing cell name",
                                    "Scotts MMI requires a cell name.",
                                )
                                return
                            df = self.mw.s.transforms.append_mmi(df, "Scotts", cell_name=cell_name)
                        else:
                            df = self.mw.s.transforms.append_mmi(df, mmi_type)
                    except Exception as e:
                        QMessageBox.critical(self.mw, "MMI Error", str(e))
                        return

                # -------------------- Seeds --------------------
                seed_opts = opts.get("seeds", {})
                if seed_opts.get("enabled"):
                    seed_key = seed_opts.get("value")
                    try:
                        seed_rows = seed_dict[seed_key][1]
                        df = self.mw.s.transforms.append_seeds(df, seed_rows)
                    except Exception as e:
                        QMessageBox.critical(self.mw, "Seed Error", str(e))
                        return

                # -------------------- Preview/Edit --------------------
                preview = PreviewDialog(df, self.mw)
                if preview.exec() != QDialog.Accepted:
                    return
                df = preview.get_dataframe()

                # Clean newlines before save
                df = df.map(lambda x: str(x).replace("\n", " ").strip())

                delimiter = opts.get("delimiter", ",")
                base = os.path.splitext(os.path.basename(infile))[0]
                default_name = f"{base}.csv"
                outfile = self.mw.ask_save_csv(
                    "Save output file",
                    "CSV Files (*.csv);;All Files (*)",
                    defaultName=default_name,
                )
                if not outfile:
                    return

                def job_save():
                    self.mw._save_csv(df, outfile, has_header=has_header, delimiter=delimiter)
                    return True

                self.mw._run_busy(
                    "Create File",
                    "Saving file…",
                    job_save,
                    on_done=lambda _: self.mw.s.logger.log("File created successfully.", "green"),
                    on_err=lambda e: QMessageBox.critical(self.mw, "Save Error", e),
                )

            except Exception as e:
                QMessageBox.critical(self.mw, "Error", str(e))

        self.mw._run_busy("Create File", "Loading file…", job_load, on_done=on_loaded, on_err=on_err)

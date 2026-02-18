# workspace/create_file.py
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from config.schemas import CREATE_FILE_SCHEMA
from config.seeds import seed_dict
from workspace.base import BaseWorkflow


class CreateFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose File",
            "Files (*.csv *.txt *.f *.xls *.xlsx);;All Files (*)",
        )
        if not infile:
            return

        opts = self.options_dialog(CREATE_FILE_SCHEMA, title="Create File Options")
        if not opts:
            return

        header_mode = opts.get("header_cleaning", "none")

        def on_loaded(df, has_header: bool):
            # -------------------- MMI --------------------
            mmi_opts = opts.get("mmi", {}) or {}
            if mmi_opts.get("enabled"):
                mmi_type = mmi_opts.get("value")
                try:
                    if mmi_type == "Scotts":
                        cell_name = (mmi_opts.get("cell_name") or "").strip()
                        if not cell_name:
                            self.warn("Missing cell name", "Scotts MMI requires a cell name.")
                            return
                        df_mmi = self.mw.s.transforms.append_mmi(df, "Scotts", cell_name=cell_name)
                    else:
                        df_mmi = self.mw.s.transforms.append_mmi(df, mmi_type)
                    df = df_mmi
                except Exception as e:
                    QMessageBox.critical(self.mw, "MMI Error", str(e))
                    return

            # -------------------- Seeds --------------------
            seed_opts = opts.get("seeds", {}) or {}
            if seed_opts.get("enabled"):
                seed_key = seed_opts.get("value")
                try:
                    seed_rows = seed_dict[seed_key][1]
                    df = self.mw.s.transforms.append_seeds(df, seed_rows)
                except Exception as e:
                    QMessageBox.critical(self.mw, "Seed Error", str(e))
                    return

            # -------------------- Preview/Edit --------------------
            edited = self.preview_dialog(df, title="Preview")
            if edited is None:
                return
            df = edited

            # -------------------- Save --------------------
            delimiter = opts.get("delimiter", ",")
            outfile = self.ask_save_csv_default_from_infile(
                infile,
                title="Save output file",
                suffix=".csv",
                filter="CSV Files (*.csv);;All Files (*)",
            )
            if not outfile:
                return

            self.save_csv_then(
                df,
                outfile,
                title="Create File",
                delimiter=delimiter,
                has_header=has_header,
                success_msg="File created successfully.",
                sanitize=True,  # keeps your existing newline cleanup behavior
            )

        # CreateFile previously did NOT call make_file_writable() on infile
        self.load_df_then(
            infile,
            title="Create File",
            header_mode=header_mode,
            make_writable=False,
            on_loaded=on_loaded,
        )

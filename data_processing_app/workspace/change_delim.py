# workspace/change_delim.py
from __future__ import annotations

from config.schemas import CHANGE_DELIM_SCHEMA
from workspace.base import BaseWorkflow


class ChangeDelimiter(BaseWorkflow):
    """
    Workflow:
      - ask for input CSV/TXT
      - load via FileLoader
      - ask for output delimiter
      - ask for output path
      - save
    """

    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose CSV/TXT file to load",
            "CSV/TXT Files (*.csv *.txt);;All Files (*)",
        )
        if not infile:
            return

        opts = self.options_dialog(
            CHANGE_DELIM_SCHEMA,
            title="Change CSV Delimiter",
        )
        if not opts:
            return

        out_delim = opts.get("delimiter")
        if not out_delim:
            return

        def on_loaded(df, has_header: bool):
            outfile = self.ask_save_csv_default_from_infile(
                infile,
                title="Save CSV as",
                suffix=".csv",
                filter="CSV Files (*.csv);;All Files (*)",
            )
            if not outfile:
                return

            self.save_csv_then(
                df,
                outfile,
                title="Change CSV Delimiter",
                delimiter=out_delim,
                has_header=has_header,
                success_msg="File created successfully.",
                sanitize=False,  # delimiter change does not need newline cleanup
            )

        # ChangeDelimiter previously *did* call make_file_writable
        self.load_df_then(
            infile,
            title="Change CSV Delimiter",
            make_writable=True,
            on_loaded=on_loaded,
        )

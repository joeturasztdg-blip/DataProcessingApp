import os
from PySide6.QtWidgets import QDialog, QMessageBox

from config.schemas import SPLIT_FILE_SCHEMA
from config.seeds import seed_dict
from gui.dialogs import OptionsDialog, PreviewDialog


class SplitFile:
    def __init__(self, mw):
        self.mw = mw

    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose file to split",
            "CSV/TXT/Excel Files (*.csv *.txt *.xls *.xlsx);;All Files (*)",)
        if not infile:
            return

        self.mw.make_file_writable(infile)

        def job_load():
            return self.mw.s.loader.load_file(infile)

        def on_err(err_text: str):
            self.mw.show_error("Split file failed", err_text)

        def on_loaded(result):
            try:
                df, has_header = result
                if df is None:
                    return

                if df.columns is None or len(df.columns) == 0:
                    QMessageBox.critical(self.mw, "Split File", "No columns found in file.")
                    return

                MAX_UNIQUE = 20

                def unique_count_up_to(series, limit: int):
                    seen = set()
                    has_non_blank = False

                    for v in series.astype(str):
                        s = v.strip()
                        if s:
                            has_non_blank = True
                            seen.add(s)
                            if len(seen) > limit:
                                return len(seen), has_non_blank

                    return len(seen), has_non_blank

                eligible = []
                for c in df.columns:
                    try:
                        n, has_non_blank = unique_count_up_to(df[c], MAX_UNIQUE)
                    except Exception:
                        continue
                    if has_non_blank and n <= MAX_UNIQUE:
                        eligible.append((str(c), n))

                if not eligible:
                    QMessageBox.critical(
                        self.mw,
                        "Split File",
                        f"No suitable columns found to split on (must have {MAX_UNIQUE} or fewer unique values).",
                    )
                    return

                col_options = [("Select a column", "__select__")]
                for col_name, n in sorted(eligible, key=lambda t: (t[0].casefold(), t[1])):
                    col_options.append((f"{col_name} ({n})", col_name))
                # ----------------------------- Dynamic Dialog -----------------------------
                def values_provider(col_name: str):
                    if not col_name or col_name == "__select__" or col_name not in df.columns:
                        return []
                    s = df[col_name].astype(str).map(lambda x: x.strip())
                    uniq = sorted(set(s.tolist()), key=lambda t: t.casefold())
                    return [("(blank)" if v == "" else v, v) for v in uniq]

                schema = [dict(x) for x in SPLIT_FILE_SCHEMA]

                schema[0]["options"] = col_options
                schema[0]["default"] = "__select__"

                schema[1]["depends_on"] = "split_column"
                schema[1]["options_provider"] = values_provider
                schema[1]["options"] = []

                schema[2]["depends_on"] = "split_column"
                schema[2]["options_provider"] = values_provider
                schema[2]["options"] = []

                dlg = OptionsDialog(schema, parent=self.mw, title="Split File Options")
                if dlg.exec() != QDialog.Accepted:
                    return
                opts = dlg.get_results()
                # ----------------------------------------------------------
                split_col = opts.get("split_column")
                if not split_col or split_col == "__select__":
                    QMessageBox.warning(self.mw, "Missing column", "Please select a column to split by.")
                    return

                file1_vals = set(opts.get("file1_values") or [])
                file2_vals = set(opts.get("file2_values") or [])

                if not file1_vals and not file2_vals:
                    QMessageBox.warning(
                        self.mw,
                        "Missing groups",
                        "Select at least one value for File 1 or File 2.",
                    )
                    return

                overlap = file1_vals & file2_vals
                if overlap:
                    QMessageBox.warning(
                        self.mw,
                        "Overlapping values",
                        "Some values are selected for both File 1 and File 2. "
                        "Please select each value only once.",
                    )
                    return
                # ----------------------------- Split -----------------------------
                series = df[split_col].astype(str).map(lambda x: x.strip())
                mask1 = series.isin(file1_vals)
                mask2 = series.isin(file2_vals)

                file1_df = df[mask1].copy()
                file2_df = df[mask2].copy()

                has_header_1 = has_header_2 = has_header
                # ----------------------------- Seeds -----------------------------
                seed_opts = opts.get("seeds", {})
                if seed_opts.get("enabled"):
                    seed_key = seed_opts.get("value")
                    seeds = seed_dict.get(seed_key, (None, None))[1]
                    if seeds:
                        file1_df = self.mw.s.transforms.append_seeds(file1_df, seeds)
                # ----------------------------- Preview -----------------------------
                p1 = PreviewDialog(file1_df, self.mw, title="File 1 Preview")
                if p1.exec() != QDialog.Accepted:
                    return
                file1_df = p1.get_dataframe()

                p2 = PreviewDialog(file2_df, self.mw, title="File 2 Preview")
                if p2.exec() != QDialog.Accepted:
                    return
                file2_df = p2.get_dataframe()
                # ----------------------------- Save -----------------------------
                out_delim = opts.get("delimiter", ",")
                if not out_delim:
                    return

                raw_base = os.path.splitext(os.path.basename(infile))[0]
                base = raw_base[:-4] + " " if raw_base.upper().endswith(".OUT") else raw_base

                default_1 = f"{base} P1.csv"
                default_2 = f"{base} P2.csv"

                out1 = self.mw.ask_save_csv(
                    "Save File 1 (P1)",
                    "CSV Files (*.csv);;All Files (*)",
                    defaultName=default_1,
                )
                if not out1:
                    return

                out2 = self.mw.ask_save_csv(
                    "Save File 2 (P2)",
                    "CSV Files (*.csv);;All Files (*)",
                    defaultName=default_2,
                )
                if not out2:
                    return
                
                file1_df = file1_df.map(lambda x: str(x).replace("\n", " ").strip())
                file2_df = file2_df.map(lambda x: str(x).replace("\n", " ").strip())

                def job_save():
                    self.mw._save_csv(file1_df, out1, has_header=has_header_1, delimiter=out_delim)
                    self.mw._save_csv(file2_df, out2, has_header=has_header_2, delimiter=out_delim)
                    return True

                self.mw._run_busy(
                    "Split File",
                    "Saving files…",
                    job_save,
                    on_done=lambda _: self.mw.s.logger.log("Files created successfully.", "green"),
                    on_err=lambda e: self.mw.show_error("Split file failed", e),
                )

            except Exception as e:
                self.mw.show_error("Split file failed", str(e))

        self.mw._run_busy("Split File", "Loading file…", job_load, on_done=on_loaded, on_err=on_err)

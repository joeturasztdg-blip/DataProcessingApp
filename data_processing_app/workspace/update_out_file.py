from __future__ import annotations

from config.schemas import UPDATE_OUT_FILE_SCHEMA
from workspace.base import BaseWorkflow


class UpdateOutFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose CSV/TXT to update",
            "CSV/TXT/(*.OUT.csv *.OUT.txt);;All Files (*)")
        if not infile:
            return

        opts = self.options_dialog(UPDATE_OUT_FILE_SCHEMA, title="Update Out File")
        if not opts:
            return

        def on_loaded(df, has_header: bool):
            try:
                # ---- UCID updates ----
                ucid_opts = opts.get("ucid_updates", {}) or {}
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

                outfile = infile
                if not outfile:
                    return

                delimiter = opts.get("delimiter", ",")

                self.save_csv_then(
                    df,
                    outfile,
                    title="Update OUT File",
                    delimiter=delimiter,
                    has_header=has_header,
                    success_msg="OUT file updated successfully.",
                    sanitize=False)

            except Exception as e:
                self.fail_exception("Update OUT file failed", e)

        self.load_df_then(
            infile,
            title="Update OUT File",
            make_writable=True,
            on_loaded=on_loaded)
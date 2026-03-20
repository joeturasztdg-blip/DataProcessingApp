from __future__ import annotations

from config.schemas import UPDATE_OUT_FILE_SCHEMA
from workspace.base import BaseWorkflow


class UpdateOutFile(BaseWorkflow):
    def run(self, checked: bool = False):
        infile = self.mw.ask_open_file(
            "Choose CSV/TXT to update",
            "CSV/TXT/(*.OUT.csv *.OUT.txt);;All Files (*)",
        )
        if not infile:
            return

        opts = self.options_dialog(UPDATE_OUT_FILE_SCHEMA, title="Update Out File")
        if not opts:
            return

        def on_loaded(df, has_header: bool):
            try:
                # ---- UCID updates ----
                ucid_mode = str(opts.get("ucid_updates", "none") or "none").strip()

                ucid1 = str(opts.get("ucid1", "") or "").strip()
                ucid2 = str(opts.get("ucid2", "") or "").strip()

                ucid_map = {}

                if ucid_mode == "1":
                    if ucid1:
                        ucid_map["UCID1"] = ucid1
                        ucid_map["UCID2"] = ucid1

                elif ucid_mode == "2":
                    if ucid1:
                        ucid_map["UCID1"] = ucid1
                    if ucid2:
                        ucid_map["UCID2"] = ucid2

                if ucid_map:
                    df = self.mw.s.transforms.update_UCID(df, ucid_map)

                # ---- Barcode padding ----
                padding_choice = str(opts.get("barcode_padding", "none") or "none")
                if padding_choice != "none":
                    df = self.mw.s.transforms.apply_barcode_padding(df, padding_choice)

                delimiter = opts.get("delimiter", ",")

                self.save_csv_then(
                    df,
                    infile,
                    title="Update OUT File",
                    delimiter=delimiter,
                    has_header=has_header,
                    success_msg="OUT file updated successfully.",
                    sanitize=False,
                )

            except Exception as e:
                self.fail_exception("Update OUT file failed", e)

        self.load_df_then(
            infile,
            title="Update OUT File",
            make_writable=True,
            on_loaded=on_loaded,
        )
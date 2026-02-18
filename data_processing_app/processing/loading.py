import os, csv, io, pandas as pd, msoffcrypto
from utils.table_utils import pad_rows, make_unique_columns
from config.constants import CSV_SNIFF_BYTES
from workspace.jobs import CANCELLED_MSG

class FileLoader:
    def __init__(self, header_detector, cleaner, logger, password_callback):
        self.headers = header_detector
        self.cleaner = cleaner
        self.logger = logger
        self.password_callback = password_callback
        
    def _check_cancel(self, cancel_event) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError(CANCELLED_MSG)

    def load_file(self, filename, header_cleaning_mode="none", cancel_event=None):
        self.logger.log(f"[LOAD] Loading file: {os.path.basename(filename)}", "green")
        self._check_cancel(cancel_event)


        if filename.lower().endswith((".csv", ".txt", ".f")):
            return self._load_csv(filename, header_cleaning_mode, cancel_event=cancel_event)
        if filename.lower().endswith((".xls", ".xlsx")):
            return self._load_excel(filename, header_cleaning_mode, cancel_event=cancel_event)
        raise ValueError("Unsupported file type")

    def _load_csv(self, filename, header_cleaning_mode="none", cancel_event=None):
        delimiter = self._detect_delimiter(filename)
        rows = []
        with open(filename, encoding="utf-8", errors="ignore") as f:
            rdr = csv.reader(f, delimiter=delimiter)
            for row in rdr:
                self._check_cancel(cancel_event)
                rows.append(row)
        return self._process_rows(rows, header_cleaning_mode=header_cleaning_mode, cancel_event = cancel_event)

    def _load_excel(self, filename, header_cleaning_mode="none", cancel_event=None):
        self._check_cancel(cancel_event)
        # ---- Normal Read ----
        normal_exc = None
        try:
            df = pd.read_excel(filename, header=None, dtype=str).fillna("")
            self._check_cancel(cancel_event)
            return self._process_rows(df.values.tolist(), header_cleaning_mode=header_cleaning_mode, cancel_event=cancel_event)
        except Exception as e:
            normal_exc = e
            if not self.password_callback:
                raise
        # ---- Encrypted Read ----
        with open(filename, "rb") as f:
            office = msoffcrypto.OfficeFile(f)
            if not office.is_encrypted():
                raise normal_exc

        while True:
            self._check_cancel(cancel_event)
            password = self.password_callback("Enter password:")
            if password is None:
                self.logger.log("[LOAD] Password entry cancelled.", "yellow")
                return None, None

            password = str(password).strip()
            if not password:
                self.logger.log("[LOAD] Empty password entered.", "yellow")
                continue

            try:
                self._check_cancel(cancel_event)

                decrypted = io.BytesIO()
                with open(filename, "rb") as f:
                    office = msoffcrypto.OfficeFile(f)
                    office.load_key(password=password)
                    office.decrypt(decrypted)

                self._check_cancel(cancel_event)

                decrypted.seek(0)
                df = pd.read_excel(decrypted, header=None, dtype=str).fillna("")

                self._check_cancel(cancel_event)

                return self._process_rows(df.values.tolist(), header_cleaning_mode=header_cleaning_mode, cancel_event=cancel_event)

            except RuntimeError as e:
                if str(e) == CANCELLED_MSG:
                    raise
                raise
            except Exception:
                self.logger.log("[LOAD] Incorrect password — try again or cancel.", "red")

    def _process_rows(self, rows, header_cleaning_mode="none", cancel_event=None):
        self._check_cancel(cancel_event)
        if len(rows) < 4:
            raise ValueError("Invalid file.")

        r1, r2, r3 = rows[:3]
        result = self.headers.detect_header(r1, r2, r3)
        self.headers.last_header_result = result

        has_header, cols, data = self.headers.apply_header_result(result, rows)
        padded, max_cols = pad_rows(data)
        self._check_cancel(cancel_event)

        if len(cols) < max_cols:
            cols += [f"Column{len(cols) + i + 1}" for i in range(max_cols - len(cols))]

        df = pd.DataFrame(padded, columns=cols).astype(object)
        df = self.cleaner.cleanse_dataframe(df)
        df, has_header = self.headers.analyze_and_log_header(df, has_header)
        self._check_cancel(cancel_event)
        df = self.cleaner.clean_header_names(df,has_header,mode=header_cleaning_mode,)

        if has_header:
            new_cols = make_unique_columns(df.columns)
            if list(df.columns) != new_cols:
                self.logger.log("[HEADER] Renamed duplicate columns","yellow",)
                df.columns = new_cols
        return df, has_header

    def _detect_delimiter(self, filename):
        with open(filename, encoding="utf-8", errors="ignore") as f:
            sample = f.read(CSV_SNIFF_BYTES)
        candidates = [",", ";", "\t", "|"]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="".join(candidates))
            return dialect.delimiter
        except Exception:
            pass

        counts = {d: sample.count(d) for d in candidates}
        best = max(counts, key=counts.get)
        if counts[best] < 2:
            return ","
        return best
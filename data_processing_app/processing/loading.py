import os, csv, io, pandas as pd, msoffcrypto
from utils.row_utils import pad_rows
from utils.col_utils import make_unique_columns

class FileLoader:
    def __init__(self, header_detector, cleaner, logger, password_callback):
        self.headers = header_detector
        self.cleaner = cleaner
        self.logger = logger
        self.password_callback = password_callback

    def load_file(self, filename, header_cleaning_mode="none"):
        self.logger.log(f"[LOAD] Loading file: {os.path.basename(filename)}", "green")
        if filename.lower().endswith((".csv",".txt",".f")):
            return self._load_csv(filename, header_cleaning_mode)
        if filename.lower().endswith((".xls",".xlsx")):
            return self._load_excel(filename, header_cleaning_mode)
        raise ValueError("Unsupported file type")

    def _load_csv(self, filename, header_cleaning_mode="none"):
        delimiter = self._detect_delimiter(filename)
        with open(filename, encoding="utf-8", errors="ignore") as f:
            rows = list(csv.reader(f, delimiter=delimiter))
        return self._process_rows(rows, header_cleaning_mode=header_cleaning_mode)

    def _load_excel(self, filename, header_cleaning_mode="none"):
        # Normal read
        try:
            df = pd.read_excel(filename, header=None, dtype=str).fillna("")
            return self._process_rows(df.values.tolist(), header_cleaning_mode=header_cleaning_mode)
        except Exception:
            if not self.password_callback:
                raise

        # Check encrypted
        with open(filename, "rb") as f:
            office = msoffcrypto.OfficeFile(f)
            if not office.is_encrypted():
                raise

        while True:
            password = self.password_callback("Enter password:")
            # Cancel
            if password is None:
                self.logger.log("[LOAD] Password entry cancelled.", "yellow")
                return None, None

            password = str(password).strip()
            if not password:
                self.logger.log("[LOAD] Empty password entered.", "yellow")
                continue

            try:
                decrypted = io.BytesIO()
                with open(filename, "rb") as f:
                    office = msoffcrypto.OfficeFile(f)
                    office.load_key(password=password)
                    office.decrypt(decrypted)

                decrypted.seek(0)
                df = pd.read_excel(decrypted, header=None, dtype=str).fillna("")
                return self._process_rows(df.values.tolist(), header_cleaning_mode=header_cleaning_mode)

            except Exception:
                self.logger.log("[LOAD] Incorrect password — try again or cancel.", "red")


    def _process_rows(self, rows, header_cleaning_mode="none"):
        if len(rows) < 4:
            raise ValueError("Invalid file.")
        
        r1, r2, r3 = rows[:3]
        result = self.headers.detect_header(r1, r2, r3)
        self.headers.last_header_result = result

        has_header, cols, data = self.headers.apply_header_result(result, rows)
        padded, max_cols = pad_rows(data)

        if len(cols) < max_cols:
            cols += [f"Column{len(cols)+i+1}" for i in range(max_cols - len(cols))]

        df = pd.DataFrame(padded, columns=cols).astype(object)
        df = self.cleaner.cleanse_dataframe(df)
        df, has_header = self.headers.analyze_and_log_header(df, has_header)
        df = self.cleaner.clean_header_names(
            df,
            has_header,
            mode=header_cleaning_mode,
        )

        if has_header:
            new_cols = make_unique_columns(df.columns)
            if list(df.columns) != new_cols:
                self.logger.log(
                    "[HEADER] Renamed duplicate columns (A → A (1), A (2), …)",
                    "yellow",
                )
                df.columns = new_cols
        return df, has_header

    def _detect_delimiter(self, filename):
        with open(filename, encoding="utf-8", errors="ignore") as f:
            sample = f.read(8192)
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
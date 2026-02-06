import os, csv, io, pandas as pd, msoffcrypto
from utils.row_utils import pad_rows

class FileLoader:
    def __init__(self, header_detector, cleaner, logger, password_callback):
        self.headers = header_detector
        self.cleaner = cleaner
        self.logger = logger
        self.password_callback = password_callback

    def load_file(self, filename):
        self.logger.log(f"[LOAD] Loading file: {os.path.basename(filename)}", "green")
        if filename.lower().endswith((".csv",".txt",".f")):
            return self._load_csv(filename)
        if filename.lower().endswith((".xls",".xlsx")):
            return self._load_excel(filename)
        raise ValueError("Unsupported file type")

    def _load_csv(self, filename):
        delimiter = self._detect_delimiter(filename)
        with open(filename, encoding="utf-8", errors="ignore") as f:
            rows = list(csv.reader(f, delimiter=delimiter))
        return self._process_rows(rows)

    def _load_excel(self, filename):
        try:
            df = pd.read_excel(filename, header=None, dtype=str).fillna("")
            return self._process_rows(df.values.tolist())
        except Exception:
            if not self.password_callback:
                raise

        with open(filename, "rb") as f:
            office = msoffcrypto.OfficeFile(f)
            if not office.is_encrypted():
                raise

        password = self.password_callback("Excel file is password protected:")
        decrypted = io.BytesIO()
        with open(filename, "rb") as f:
            office = msoffcrypto.OfficeFile(f)
            office.load_key(password=password)
            office.decrypt(decrypted)

        decrypted.seek(0)
        df = pd.read_excel(decrypted, header=None, dtype=str).fillna("")
        return self._process_rows(df.values.tolist())

    def _process_rows(self, rows):
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
        df = self.cleaner.clean_header_names(df, has_header)

        return df, has_header

    def _detect_delimiter(self, filename):
        with open(filename, encoding="utf-8", errors="ignore") as f:
            sample = f.read(8192)
        for d in [",",";","\t","|"]:
            if sample.count(d) > 2:
                return d
        return ","

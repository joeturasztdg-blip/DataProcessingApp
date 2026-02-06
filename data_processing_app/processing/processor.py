import re
import os
import io
import sys
import csv
import pandas as pd
import shutil
import string
import secrets
import subprocess
import msoffcrypto

from collections import Counter
from pandas.api.types import is_object_dtype

from utils.formatting import color

class Processor:
    CONTROL_CHARS = ''.join(map(chr, range(0, 32)))
    CONTROL_REGEX = re.compile(f"[{re.escape(CONTROL_CHARS)}]")

    def __init__(self, logger=None, password_callback=None):
        self.logger = logger or (lambda m, c=None: None)
        self.password_callback = password_callback

        self.cleansing_stats = Counter()
        self.last_header_result = None
        self.dropped_header_announced = False


    def log(self, msg, colour=None):
        try:
            if colour:
                self.logger(color(msg, colour), None)
            else:
                self.logger(msg, None)
        except TypeError:
            self.logger(msg, colour)

    # -------------------- cleansing --------------------
    def normalise_row(self, row):
        return ["" if c is None else str(c).strip() for c in row]

    def cleanse_cell_string(self, x):
        if not isinstance(x, str):
            return x
        removed_count = 0
        s = x
        matches = re.findall(r"_x0{3}[0-9A-Fa-f]{1}_", s)
        if matches:
            removed_count += sum(len(m) for m in matches)
            s = re.sub(r"_x0{3}[0-9A-Fa-f]{1}_", " ", s)
        control_matches = self.CONTROL_REGEX.findall(s)
        removed_count += len(control_matches)
        s = self.CONTROL_REGEX.sub(" ", s)
        removed_nbsp = s.count("\xa0")
        removed_count += removed_nbsp
        if removed_nbsp:
            s = s.replace("\xa0", " ")
        if removed_count > 0:
            self.cleansing_stats['removed_chars'] += removed_count
            self.cleansing_stats['modified_cells'] += 1
        return s

    def cleanse_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        self.cleansing_stats.clear()
        df = df.astype(object).where(pd.notnull(df), "")
        df = df.map(self.cleanse_cell_string)
        df = df.replace("", pd.NA)
        before_rows, before_cols = df.shape
        df = df.dropna(how="all")
        
        cols_to_drop = []
        for i, col in enumerate(df.columns):
            col_data = df.iloc[:, i]
            col_data_empty = bool(col_data.isna().all())
            header = str(col).strip()
            is_placeholder = not header or re.fullmatch(r"Column\d+", header)
            if col_data_empty and is_placeholder:
                cols_to_drop.append(col)
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            
        after_rows, after_cols = df.shape
        df = df.fillna("")
        removed = self.cleansing_stats.get("removed_chars", 0)
        modified = self.cleansing_stats.get("modified_cells", 0)
        if removed > 0:
            self.log(f"Removed {removed} hidden characters from {modified} cells.", "yellow")
        dropped_rows = before_rows - after_rows
        dropped_cols = before_cols - after_cols
        if dropped_rows > 0:
            self.log(f"Dropped {dropped_rows} empty rows", "yellow")
        if dropped_cols > 0:
            self.log(f"Dropped {dropped_cols} empty columns.", "yellow")
        return df
    
    def clean_header_names(self, df: pd.DataFrame, has_header: bool) -> pd.DataFrame:
        if not has_header:
            return df
        original = list(df.columns)
        cleaned = [
            c.replace("_", " ").strip() if isinstance(c, str) else c
            for c in original]
        if original != cleaned:
            self.log("[HEADER] Replaced underscores with spaces in column names.", "yellow")
            df.columns = cleaned
        return df

    def pad_rows(self, rows):
        if not rows:
            return rows, 0
        max_cols = 0
        for r in rows:
            if len(r) > max_cols:
                max_cols = len(r)
        if max_cols == 0:
            return rows, 0
        padded = []
        for r in rows:
            if len(r) == max_cols:
                padded.append(r)
            else:
                new = r + [""] * (max_cols - len(r))
                padded.append(new)
        return padded, max_cols

    def append_seeds(self, df: pd.DataFrame, seeds):
        if not seeds:
            return df
        ncols = len(df.columns)
        padded_seeds = [s + [""] * max(0, ncols - len(s)) for s in seeds]
        seed_df = pd.DataFrame(padded_seeds, columns=list(df.columns)[:ncols])
        return pd.concat([df, seed_df], ignore_index=True)

    def append_mmi(self, df: pd.DataFrame, mmi_choice, cell_name=None, new_col_name="MMI"):
        if mmi_choice == "Coopers":
            col_a = df.columns[0]
            col_c = df.columns[2] if len(df.columns) > 2 else df.columns[0]
            df[new_col_name] = ("Y|" + df[col_a].astype(str).str.strip() + "|" + df[col_c].astype(str).str.strip())
        elif mmi_choice == "Scotts":
            if not cell_name:
                raise ValueError("Cell name is required for Scotts MMI")
            col_a = df.columns[0]
            df[new_col_name] = (df[col_a].astype(str).str.strip() + "|" + cell_name.strip())
        elif mmi_choice == "ProHub DMS":
            col_a = df.columns[0]
            col_b = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            col_g = df.columns[6] if len(df.columns) > 6 else df.columns[0]
            df[new_col_name] = (df[col_g].astype(str).str.strip().str[:-12] + "00" + df[col_a].astype(str).str.strip() + df[col_b].astype(str).str.strip().str[1:])
        return df

    def remove_cols(self, df: pd.DataFrame):
        base_cols = ["BagNo", "ItemNo", "SscZone", "Carrier", "Depot", "BagBreak", "BarcodeData"]
        remove = [c for c in base_cols if c in df.columns]
        return df.drop(columns=remove, errors="ignore")

    def find_7zip(self):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            exe_path = os.path.join(bundle_dir, "7z")
            if os.path.isfile(exe_path):
                return exe_path
            exe_path_exe = os.path.join(bundle_dir, "7z.exe")
            if os.path.isfile(exe_path_exe):
                return exe_path_exe
        candidates = ["7z", "7za", "7zr",
            r"C:\\Program Files\\7-Zip\\7z.exe",
            r"C:\\Program Files (x86)\\7-Zip\\7z.exe",
            "/usr/local/bin/7z",
            "/opt/homebrew/bin/7z",
            "/usr/bin/7z"]
        for c in candidates:
            path = shutil.which(c) or (c if os.path.isfile(c) else None)
            if path:
                return path
        return None
    
    def generate_random_password(self, length=16):
        SAFE_CHARS = string.ascii_letters + string.digits + "-_@#$^!=+"
        return ''.join(secrets.choice(SAFE_CHARS) for _ in range(length))

    def create_encrypted_zip(self, folder, zip_filename, password):
        seven = self.find_7zip()
        if seven is None:
            raise FileNotFoundError("7-Zip not found on PATH.")
        folder_contents = os.path.join(folder, "*")
        cmd = [seven, "a", "-tzip", zip_filename, folder_contents, f"-p{password}", "-mem=ZipCrypto"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"7-Zip failed: {result.stderr}")
        return True

    def get_row_sig(self, row):
        signature = []
        for cell in row:
            text = str(cell).strip()
            has_alpha = any(c.isalpha() for c in text)
            has_digit = any(c.isdigit() for c in text)
            cell_len = len(text)
            signature.append((has_alpha, has_digit, cell_len))
        return signature

    def score_row_similarity(self, sig_a, sig_b):
        score = 0
        for (a_alpha, a_digit, _), (b_alpha, b_digit, _) in zip(sig_a, sig_b):
            if a_alpha == b_alpha:
                score += 1
            if a_digit == b_digit:
                score += 1
        return score

    def row_digit_count(self, row):
        return sum(any(c.isdigit() for c in str(cell)) for cell in row)

    def row_avg_word_length(self, row):
        total = 0
        count = 0
        for cell in row:
            s = str(cell).strip()
            if not s:
                continue
            l = len(s)
            total += l
            count += 1
        return (total / count) if count else 0.0

    def uses_similarity_rule(self, r1, r2, r3):
        sig1 = self.get_row_sig(r1)
        sig2 = self.get_row_sig(r2)
        sig3 = self.get_row_sig(r3)
        sim12 = self.score_row_similarity(sig1, sig2)
        sim23 = self.score_row_similarity(sig2, sig3)
        return sim12 < sim23 * 0.75

    def uses_digit_density_rule(self, r1, r2, r3):
        d1 = self.row_digit_count(r1)
        d2 = self.row_digit_count(r2)
        d3 = self.row_digit_count(r3)
        return d1 < min(d2, d3) / 2

    def uses_word_length_rule(self, r1, r2, r3):
        l1 = self.row_avg_word_length(r1)
        l2 = self.row_avg_word_length(r2)
        l3 = self.row_avg_word_length(r3)
        return l1 > max(l2, l3) * 1.3

    def header_contains_keywords(self, row):
        HEADER_KEYWORDS = {
            "name", "address", "postcode", "post code", "zip", "email",
            "city", "town", "county", "country",
            "a1", "a2", "a3", "a4", "a5", "a6",
            "seed", "pid", "contact_id", "marketing_campaign", "brand_cd", "dps"
        }

        tokens = {
            str(c).strip().lower()
            for c in row
            if str(c).strip()
        }

        return bool(tokens & HEADER_KEYWORDS)


    def detect_delimiter(self, filename):
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
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

    def split_raw_lines(self, filename, delimiter):
        split_lines = []
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                split_lines.append(row)
        return split_lines

    def is_csv(self, name):
        return name.lower().endswith((".csv", ".txt", ".f"))

    def is_excel(self, name):
        return name.lower().endswith((".xls", ".xlsx"))

    def process_loaded_rows(self, lines):
        if len(lines) < 4:
            raise ValueError("Invalid file.")
        row1, row2, row3 = lines[0], lines[1], lines[2]
        result = self.detect_header(row1, row2, row3)
        self.last_header_result = result
        has_header, col_names, data_rows = self.apply_header_result(result, lines)
        padded_rows, max_cols = self.pad_rows(data_rows)
        if len(col_names) < max_cols:
            col_names += [f"Column{len(col_names) + i + 1}" for i in range(max_cols - len(col_names))]
        df = pd.DataFrame(padded_rows, columns=col_names).astype(object)
        df = self.cleanse_dataframe(df)
        return df, has_header

    def load_csv(self, filename):
        delimiter = self.detect_delimiter(filename)
        raw_lines = self.split_raw_lines(filename, delimiter)
        return self.process_loaded_rows(raw_lines)

    def load_excel(self, filename):
        try:
            raw_df = pd.read_excel(filename, header=None, dtype=str).fillna("")
            raw_lines = raw_df.values.tolist()
            return self.process_loaded_rows(raw_lines)

        except Exception as e:
            try:
                with open(filename, "rb") as f:
                    office_file = msoffcrypto.OfficeFile(f)
                    if not office_file.is_encrypted():
                        raise

            except Exception:
                raise

            if not self.password_callback:
                raise ValueError("Encrypted Excel file but no password callback provided.")

            self.log("Encrypted file — password required", "yellow")

            password = self.password_callback("This Excel file is password protected.\nEnter password:")

            if not password:
                raise ValueError("Password entry cancelled.")
            
            try:
                decrypted = io.BytesIO()
                with open(filename, "rb") as f:
                    office_file = msoffcrypto.OfficeFile(f)
                    office_file.load_key(password=password)
                    office_file.decrypt(decrypted)
                decrypted.seek(0)
                raw_df = pd.read_excel(decrypted, header=None, dtype=str).fillna("")
                raw_lines = raw_df.values.tolist()
                return self.process_loaded_rows(raw_lines)

            except Exception as e2:
                raise ValueError("Could not open Excel file — incorrect password or unsupported encryption.") from e2

    def load_file(self, filename):
        display_name = os.path.basename(filename)
        self.log(f"[LOAD] Loading file: {display_name}", "green")

        if self.is_csv(filename):
            return self.load_csv(filename)
        elif self.is_excel(filename):
            return self.load_excel(filename)
        else:
            raise ValueError(f"Unsupported file type: {display_name}")

    def save_csv(self, df, filename, has_header=True, delimiter=","):
        df.to_csv(filename, index=False, header=has_header, sep=delimiter)
        
    def trailing_empty_run(self, row):
        cnt = 0
        for c in reversed(row):
            if str(c).strip() == "":
                cnt += 1
            else:
                break
        return cnt

    def is_duplicate_header(self, r1, r2):
        return [c.strip().lower() for c in r1] == [c.strip().lower() for c in r2]

    def detect_partial_header(self, r1, r3):
        score = 0
        if sum(1 for c in r3 if str(c).strip()) > 0 and sum(1 for c in r1 if str(c).strip()) <= max(1, int(sum(1 for c in r3 if str(c).strip()) * 0.6)):
            score += 1
        if self.trailing_empty_run(r1) > self.trailing_empty_run(r3):
            score += 1
        prefix = 0
        for c in r1:
            if str(c).strip():
                prefix += 1
            else:
                break
        if prefix > 0 and sum(1 for c in r1 if str(c).strip()) - prefix <= max(1, int(prefix * 0.2)):
            score += 1
        return score >= 2

    def detect_real_header(self, r1, r2, r3):
        if self.header_contains_keywords(r1):
            return True
        if self.uses_similarity_rule(r1, r2, r3):
            return True
        if self.uses_digit_density_rule(r1, r2, r3):
            return True
        if self.uses_word_length_rule(r1, r2, r3):
            return True
        return False

    def detect_header(self, row1, row2, row3):
        r1 = self.normalise_row(row1)
        r2 = self.normalise_row(row2)
        r3 = self.normalise_row(row3)
        if self.is_duplicate_header(r1, r2):
            return "duplicate"
        if self.detect_partial_header(r1, r3):
            return "partial"
        if self.detect_real_header(r1, r2, r3):
            return "real"
        return "none"

    def drop_useless_header(self, df, has_header):
        if not has_header:
            return df, False
        placeholder = re.compile(r"^Column\d+$")
        if all(placeholder.match(str(c)) for c in df.columns):
            if not self.dropped_header_announced:
                self.dropped_header_announced = True
            df = df.iloc[1:].reset_index(drop=True)
            return df, False
        return df, True

    def analyze_and_log_header(self, df, has_header):
        raw_result = self.last_header_result
        placeholder = re.compile(r"^Column\d+$", re.IGNORECASE)
        col_names = [str(c).strip() for c in df.columns]
        first_row = [str(v).strip() for v in df.iloc[0].tolist()] if len(df) else []
        if raw_result == "duplicate":
            if has_header and first_row and [c.lower() for c in col_names] == [v.lower() for v in first_row]:
                self.log("[HEADER] Detected duplicate header, dropping row 2.", "yellow")
                df = df.iloc[1:].reset_index(drop=True)
            else:
                self.log("[HEADER] Detected duplicate header, dropping row 2.", "yellow")
            while len(df) > 0 and [c.lower() for c in col_names] == [v.lower() for v in df.iloc[0].astype(str)]:
                df = df.iloc[1:].reset_index(drop=True)
                self.log("[HEADER] Dropped additional duplicate header row.","yellow")
        placeholder_flags = [bool(placeholder.match(c)) for c in col_names]
        if any(placeholder_flags) and not all(placeholder_flags):
            self.log("[HEADER] Detected partial header.", "yellow")
            return df, has_header
        if has_header:
            if all(placeholder.match(c) for c in col_names):
                df2, new_has = self.drop_useless_header(df, has_header)
                self.log("[HEADER] Placeholder header dropped.", "yellow")
                return df2, new_has
            if raw_result == "real":
                self.log("[HEADER] Real header confirmed.", "green")
            elif raw_result == "partial":
                self.log("[HEADER] Partial header applied.", "yellow")
            elif raw_result == "duplicate":
                pass
            else:
                self.log("[HEADER] !!UNKNOWN HEADER!!", "red")
            return df, has_header
        self.log("[HEADER] No header detected.", "yellow")
        return df, has_header

    def apply_header_result(self, result, split_lines):
        row1 = split_lines[0]
        if result == "real":
            col_names = [str(c).strip() for c in row1]
            return True, col_names, split_lines[1:]
        elif result == "duplicate":
            col_names = [str(c).strip() for c in row1]
            return True, col_names, split_lines[2:]
        elif result == "partial":
            data_rows = split_lines[1:]
            padded_data, max_cols = self.pad_rows(data_rows)
            col_names = [str(c).strip() for c in row1]
            if len(col_names) < max_cols:
                col_names += [f"Column{len(col_names)+i+1}" for i in range(max_cols - len(col_names))]
            return True, col_names, padded_data
        else:
            padded, max_cols = self.pad_rows(split_lines)
            col_names = [f"Column{i+1}" for i in range(max_cols)]
            return False, col_names, padded
    
    @staticmethod
    def split_by_zone(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if "SscZone" not in df.columns:
            raise ValueError("No 'SscZone' column — validate data.")
        ssc = df["SscZone"].astype(str).str.replace("\u00A0", " ", regex=False).str.strip()
        zone_letter = ssc.str.extract(r'([A-Za-z])\s*$', expand=False).str.upper()
        missing = zone_letter.isna()
        if missing.any():
            fallback = ssc[missing].str.rstrip().str[-1:].str.upper()
            fallback = fallback.where(fallback.str.match(r'^[A-Z]$'), other=pd.NA)
            zone_letter.loc[missing] = fallback
        is_zonal = zone_letter.isin(["A", "B"])
        zonal = df[is_zonal.fillna(False)]
        national = df[~is_zonal.fillna(False)]
        return zonal.copy(), national.copy()
    
    @staticmethod
    def update_UCID(df: pd.DataFrame, ucidMap: dict) -> pd.DataFrame:
        pattern = re.compile(r"\b(UCID1|UCID2)\b")
        def replacer(match):
            key = match.group(1)
            return f"UCID {ucidMap[key]}"
        for col in df.columns:
            col_data = df[col]
            if not isinstance(col_data, pd.Series):
                continue
            if is_object_dtype(col_data):
                df[col] = col_data.astype(str).map(lambda v: pattern.sub(replacer, v))
        return df
    
    @staticmethod
    def apply_barcode_padding(
        df: pd.DataFrame,
        padding_char: str,
        barcode_column: str = "BarcodeData"
    ) -> pd.DataFrame:
        if barcode_column not in df.columns:
            return df

        def pad(value):
            s = str(value)
            if not s:
                return s
            return s[:-1] + padding_char
        df[barcode_column] = df[barcode_column].map(pad)
        return df

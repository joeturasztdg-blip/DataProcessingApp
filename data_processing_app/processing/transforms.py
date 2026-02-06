import re
import pandas as pd
from pandas.api.types import is_object_dtype

class DomainTransforms:
    def append_seeds(self, df: pd.DataFrame, seeds):
        if not seeds:
            return df

        ncols = len(df.columns)

        padded_seeds = [
            s + [""] * max(0, ncols - len(s))
            for s in seeds
        ]

        seed_df = pd.DataFrame(
            padded_seeds,
            columns=list(df.columns)[:ncols]
        )

        return pd.concat([df, seed_df], ignore_index=True)

    def append_mmi(self, df, choice, cell_name=None, new_col="MMI"):
        if choice == "Coopers":
            df[new_col] = "Y|" + df.iloc[:,0].astype(str) + "|" + df.iloc[:,2].astype(str)
        elif choice == "Scotts":
            df[new_col] = df.iloc[:,0].astype(str) + "|" + cell_name
        return df

    def remove_cols(self, df):
        return df.drop(columns=[
            "BagNo","ItemNo","SscZone","Carrier",
            "Depot","BagBreak","BarcodeData"
        ], errors="ignore")

    @staticmethod
    def split_by_zone(df):
        if "SscZone" not in df:
            raise ValueError("No SscZone column")
        zone = df["SscZone"].astype(str).str.extract(r'([A-Za-z])$')[0]
        zonal = df[zone.isin(["A","B"])]
        national = df[~zone.isin(["A","B"])]
        return zonal.copy(), national.copy()

    @staticmethod
    def update_UCID(df, ucid_map):
        pat = re.compile(r"\b(UCID1|UCID2)\b")
        for col in df.columns:
            if is_object_dtype(df[col]):
                df[col] = df[col].astype(str).str.replace(
                    pat, lambda m: f"UCID {ucid_map[m.group(1)]}", regex=True
                )
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

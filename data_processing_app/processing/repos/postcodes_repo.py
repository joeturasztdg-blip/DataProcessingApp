from __future__ import annotations

import sqlite3
from typing import Iterable, Set, Optional

from processing.database import resolve_config_db, connect_sqlite

class PostcodesRepository:
    def __init__(self, *, db_filename: str = "postcodes.db", db_path: Optional[str] = None):
        self.db_path = db_path or resolve_config_db(db_filename)
        self.table_name = "postcodes"
        self.column_name = self._detect_postcode_column()

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path, row_factory=True)

    def _detect_postcode_column(self) -> str:
        with self._connect() as con:
            cols = [r["name"] for r in con.execute(f"PRAGMA table_info({self.table_name})").fetchall()]
        if "postcode" in cols:
            return "postcode"
        raise RuntimeError(f"postcodes.db: expected column 'postcode' in table '{self.table_name}'")

    def existing_postcode_set(self, values: Iterable[str], *, chunk_size: int = 900) -> Set[str]:
        vals = [str(v) for v in values if str(v).strip()]
        if not vals:
            return set()

        found: Set[str] = set()
        col = self.column_name

        with self._connect() as con:
            cur = con.cursor()
            for i in range(0, len(vals), int(chunk_size)):
                chunk = vals[i : i + int(chunk_size)]
                placeholders = ",".join(["?"] * len(chunk))
                sql = f"SELECT {col} AS pc FROM {self.table_name} WHERE {col} IN ({placeholders})"
                cur.execute(sql, chunk)
                found.update(str(r["pc"]) for r in cur.fetchall())

        return found
    
    def insert_postcode(self, postcode):
        postcode = postcode.strip().upper()

        with self._connect() as con:
            con.execute("INSERT OR IGNORE INTO postcodes(postcode) VALUES (?)",(postcode,),)
            con.commit()
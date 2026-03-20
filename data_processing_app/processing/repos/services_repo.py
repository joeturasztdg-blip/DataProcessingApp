from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from processing.database import resolve_config_db, connect_sqlite

class ServicesRepository:
    def __init__(self, *, db_filename: str = "services.db", db_path: Optional[str] = None):
        self.db_path = db_path or resolve_config_db(db_filename)
        self.table_name = "services"

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path, row_factory=True)
    # ---------------- Query / browser methods ----------------
    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(f"""SELECT id, name, new_code, old_code, replacement_code, max_weight_g, min_length_mm, min_width_mm,
                               min_height_mm, max_length_mm, max_width_mm, max_height_mm FROM {self.table_name}
                               ORDER BY id ASC
                               LIMIT ?""",(int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5000) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return self.list_all(limit=limit)

        pat = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(f"""SELECT id, name, new_code, old_code, replacement_code, max_weight_g, min_length_mm, min_width_mm, min_height_mm,
                               max_length_mm, max_width_mm, max_height_mm FROM {self.table_name}
                               WHERE name LIKE ? OR new_code LIKE ? OR old_code LIKE ? OR replacement_code LIKE ?
                               ORDER BY id ASC
                               LIMIT ?""",(pat, pat, pat, pat, int(limit))).fetchall()
        return [dict(r) for r in rows]

    def next_id(self) -> int:
        with self._connect() as con:
            row = con.execute(f"SELECT COALESCE(MAX(id), 0) + 1 AS nxt FROM {self.table_name}").fetchone()
        return int(row["nxt"]) if row and row["nxt"] is not None else 1

    def insert_row(self,*,id_: int,name: str,new_code: str,old_code: str,replacement_code: str,max_weight_g: int,min_length_mm: int,min_width_mm: int,
                   min_height_mm: int,max_length_mm: int | None,max_width_mm: int | None,max_height_mm: int | None,) -> None:
        with self._connect() as con:
            con.execute(f"""INSERT INTO {self.table_name} (id, name, new_code, old_code, replacement_code, max_weight_g,
                        min_length_mm, min_width_mm, min_height_mm, max_length_mm, max_width_mm, max_height_mm)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (int(id_), str(name), str(new_code), str(old_code), str(replacement_code), int(max_weight_g), int(min_length_mm),
                         int(min_width_mm), int(min_height_mm),
                         None if max_length_mm is None else int(max_length_mm),
                         None if max_width_mm is None else int(max_width_mm),
                         None if max_height_mm is None else int(max_height_mm)))
            con.commit()
    # ---------------- Ecommerce lookup methods ----------------
    def get_replacement_codes_by_new_codes(self, values, *, chunk_size: int = 900):
        vals = []
        seen = set()

        for v in values:
            key = str(v or "").strip().upper()
            if key and key not in seen:
                seen.add(key)
                vals.append(key)

        if not vals:
            return {}

        found = {}

        with self._connect() as con:
            cur = con.cursor()

            for i in range(0, len(vals), chunk_size):
                chunk = vals[i:i + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))

                cur.execute(f"""SELECT UPPER(TRIM(new_code)) AS new_code_key, replacement_code FROM {self.table_name}
                            WHERE UPPER(TRIM(new_code)) IN ({placeholders})""",chunk)
                for row in cur.fetchall():
                    found[row["new_code_key"]] = (row["replacement_code"] or "").strip()
        return found
from __future__ import annotations

import sqlite3
from typing import List, Dict, Any, Optional

from processing.database import resolve_config_db, connect_sqlite

class LoginRepository:
    def __init__(self,*,db_filename: str = "mailmark_logins.db",table_name: str = "mailmark_logins",db_path: Optional[str] = None,):
        self.table_name = table_name
        self.db_path = db_path or resolve_config_db(db_filename)

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.db_path, row_factory=True)

    def list_all(self, limit: int = 5000) -> List[Dict[str, Any]]:
        with self._connect() as con:
            rows = con.execute(f"SELECT ID, Name, Username, Password FROM {self.table_name} ORDER BY ID ASC LIMIT ?",
                (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 5000) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return self.list_all(limit=limit)

        pattern = f"%{q}%"
        with self._connect() as con:
            rows = con.execute(f"SELECT ID, Name, Username, Password FROM {self.table_name} WHERE Name LIKE ? OR Username LIKE ? ORDER BY ID ASC LIMIT ?",
                (pattern, pattern, int(limit))).fetchall()
        return [dict(r) for r in rows]

    def next_id(self) -> int:
        with self._connect() as con:
            row = con.execute(f"SELECT COALESCE(MAX(ID), 0) + 1 AS nxt FROM {self.table_name}").fetchone()
        return int(row["nxt"]) if row and row["nxt"] is not None else 1

    def insert_row(self, *, id_: int, name: str, username: str, password: str) -> None:
        with self._connect() as con:
            con.execute(
                f"INSERT INTO {self.table_name} (ID, Name, Username, Password) VALUES (?, ?, ?, ?)",
                (int(id_), str(name), str(username), str(password)),)
            con.commit()
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import aiosqlite


@dataclass(frozen=True)
class MaxAccountRecord:
    id: int
    tg_user_id: int
    max_token: str
    max_device_id: str
    title: str
    is_active: bool


class Storage:
    def __init__(self, db_path: str):
        self._db_path = db_path

    async def init(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS max_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tg_user_id INTEGER NOT NULL,
                    max_token TEXT NOT NULL,
                    max_device_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    @staticmethod
    def _row_to_account(row: Any) -> MaxAccountRecord:
        return MaxAccountRecord(
            id=int(row["id"]),
            tg_user_id=int(row["tg_user_id"]),
            max_token=str(row["max_token"]),
            max_device_id=str(row["max_device_id"]),
            title=str(row["title"] or ""),
            is_active=bool(row["is_active"]),
        )

    async def add_account(
        self,
        tg_user_id: int,
        max_token: str,
        max_device_id: str,
        title: str = "",
    ) -> MaxAccountRecord:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                INSERT INTO max_accounts (tg_user_id, max_token, max_device_id, title, is_active)
                VALUES (?, ?, ?, ?, 1)
                """,
                (tg_user_id, max_token, max_device_id, title),
            )
            await db.commit()
            acc_id = int(cur.lastrowid)
            row_cur = await db.execute(
                "SELECT * FROM max_accounts WHERE id = ?",
                (acc_id,),
            )
            row = await row_cur.fetchone()
            return self._row_to_account(row)

    async def list_accounts_for_user(self, tg_user_id: int) -> list[MaxAccountRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM max_accounts
                WHERE tg_user_id = ? AND is_active = 1
                ORDER BY id ASC
                """,
                (tg_user_id,),
            )
            rows = await cur.fetchall()
            return [self._row_to_account(row) for row in rows]

    async def list_all_active_accounts(self) -> list[MaxAccountRecord]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM max_accounts WHERE is_active = 1 ORDER BY id ASC"
            )
            rows = await cur.fetchall()
            return [self._row_to_account(row) for row in rows]

    async def get_account(self, account_id: int) -> MaxAccountRecord | None:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM max_accounts WHERE id = ?",
                (account_id,),
            )
            row = await cur.fetchone()
            return self._row_to_account(row) if row else None

    async def deactivate_account(self, account_id: int, tg_user_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                """
                UPDATE max_accounts
                SET is_active = 0
                WHERE id = ? AND tg_user_id = ? AND is_active = 1
                """,
                (account_id, tg_user_id),
            )
            await db.commit()
            return cur.rowcount > 0

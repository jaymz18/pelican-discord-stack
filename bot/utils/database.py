"""Async MariaDB access (aiomysql) with a connection pool."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import aiomysql

log = logging.getLogger("bot.db")
SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema.sql"


class Database:
    def __init__(self, host: str, port: int, user: str, password: str, database: str) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.pool: aiomysql.Pool | None = None

    @classmethod
    def from_env(cls) -> "Database":
        return cls(
            host=os.getenv("DB_HOST") or "127.0.0.1",
            port=int(os.getenv("DB_PORT") or 3306),
            user=os.getenv("DB_USERNAME") or "",
            password=os.getenv("DB_PASSWORD") or "",
            database=os.getenv("DB_DATABASE") or "",
        )

    @property
    def configured(self) -> bool:
        return bool(self.database and self.user)

    async def connect(self, retries: int = 10, delay: float = 3.0) -> None:
        last_exc: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self.pool = await aiomysql.create_pool(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    db=self.database,
                    charset="utf8mb4",
                    autocommit=True,
                    minsize=1,
                    maxsize=5,
                    pool_recycle=3600,
                    # Store all timestamps in UTC – the website converts them to its time zone.
                    init_command="SET time_zone = '+00:00'",
                )
                log.info("Connected to MariaDB (%s:%s/%s)", self.host, self.port, self.database)
                return
            except Exception as exc:  # noqa: BLE001 – connection errors come in many shapes
                last_exc = exc
                log.warning("Database connection failed (attempt %d/%d): %s", attempt, retries, exc)
                await asyncio.sleep(delay)
        raise RuntimeError("Could not connect to MariaDB") from last_exc

    async def init_schema(self) -> None:
        lines = [ln for ln in SCHEMA_FILE.read_text(encoding="utf-8").splitlines() if not ln.strip().startswith("--")]
        statements = [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
        for statement in statements:
            await self.execute(statement)
        log.info("Database schema checked (%d statements)", len(statements))

    async def close(self) -> None:
        if self.pool is not None:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None

    def _require_pool(self) -> aiomysql.Pool:
        if self.pool is None:
            raise RuntimeError("Database is not connected")
        return self.pool

    async def execute(self, query: str, *args: Any) -> int:
        """Runs a write query and returns the number of affected rows."""
        async with self._require_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args or None)
                return cur.rowcount

    async def insert(self, query: str, *args: Any) -> int:
        """Runs an INSERT and returns the new ID."""
        async with self._require_pool().acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args or None)
                return cur.lastrowid

    async def fetchone(self, query: str, *args: Any) -> dict[str, Any] | None:
        async with self._require_pool().acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, args or None)
                return await cur.fetchone()

    async def fetchall(self, query: str, *args: Any) -> list[dict[str, Any]]:
        async with self._require_pool().acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, args or None)
                return list(await cur.fetchall())

    async def ping(self) -> bool:
        try:
            row = await self.fetchone("SELECT 1 AS ok")
            return bool(row and row["ok"] == 1)
        except Exception:  # noqa: BLE001
            return False

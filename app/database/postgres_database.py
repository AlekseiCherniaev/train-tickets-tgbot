from contextlib import asynccontextmanager
from typing import AsyncIterator

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.settings import PostgresSettings


class PostgresDatabase:
    def __init__(self, settings: PostgresSettings) -> None:
        self._pool = AsyncConnectionPool(
            conninfo=(
                f"dbname={settings.db} "
                f"user={settings.user} "
                f"password={settings.password} "
                f"host={settings.host} "
                f"port={settings.port}"
            ),
            open=False,
        )

    async def start(self) -> None:
        await self._pool.open()

    async def stop(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection]:
        async with self._pool.connection() as connection:
            yield connection

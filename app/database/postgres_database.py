from contextlib import asynccontextmanager
from typing import AsyncIterator

from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool

from app.settings import PostgresSettings


class PostgresDatabase:
    def __init__(self, settings: PostgresSettings) -> None:
        self._pool = AsyncConnectionPool(
            conninfo=make_conninfo(
                dbname=settings.db,
                user=settings.user,
                password=settings.password,
                host=settings.host,
                port=settings.port,
            ),
            open=False,
        )
        self._started = False

    async def start(self) -> None:
        if self._started:
            return

        await self._pool.open()
        await self._pool.wait()

        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return

        await self._pool.close()
        self._started = False

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection]:
        async with self._pool.connection() as connection:
            yield connection

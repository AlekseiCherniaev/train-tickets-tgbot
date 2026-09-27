import logging
from datetime import date, time
from typing import Any, Mapping, override

from psycopg.rows import dict_row

from app.database import PostgresDatabase
from app.interfaces import ITicketRepository
from app.schemas import (
    NewTicketRequest,
    TicketRequest,
    TicketRequestRecord,
)


class PostgresTicketRepository(ITicketRepository):
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database
        self._logger = logging.getLogger(__name__)

    @staticmethod
    def _to_record(row: Mapping[str, Any]) -> TicketRequestRecord:
        travel_date = row["travel_date"]
        travel_time = row["travel_time"]

        if isinstance(travel_date, date):
            travel_date = travel_date.isoformat()

        if isinstance(travel_time, time):
            travel_time = travel_time.strftime("%H:%M")

        return TicketRequestRecord(
            id=row["id"],
            departure_station=row["departure_station"],
            arrival_station=row["arrival_station"],
            travel_date=travel_date,
            travel_time=travel_time,
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @override
    async def add_request(
        self,
        request: NewTicketRequest,
    ) -> int:
        query = """
            INSERT INTO ticket_requests (
                departure_station,
                arrival_station,
                travel_date,
                travel_time,
                chat_id,
                user_id,
                user_name,
                is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (
                departure_station,
                arrival_station,
                travel_date,
                travel_time,
                chat_id
            )
            WHERE is_active = TRUE
            DO UPDATE SET updated_at = NOW()
            RETURNING id
        """

        async with self._database.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    query,
                    (
                        request.departure_station,
                        request.arrival_station,
                        request.travel_date,
                        request.travel_time,
                        request.chat_id,
                        request.user_id,
                        request.user_name,
                    ),
                )

                row = await cursor.fetchone()

        if row is None:
            raise RuntimeError("Failed to create ticket request")

        request_id = int(row["id"])

        self._logger.debug(
            "Ticket request saved: id=%s, %s -> %s",
            request_id,
            request.departure_station,
            request.arrival_station,
        )

        return request_id

    @override
    async def get_request_by_id(
        self,
        request_id: int,
    ) -> TicketRequestRecord | None:
        query = """
            SELECT
                id,
                departure_station,
                arrival_station,
                travel_date,
                travel_time,
                chat_id,
                user_id,
                user_name,
                is_active,
                created_at,
                updated_at
            FROM ticket_requests
            WHERE id = %s
        """

        async with self._database.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (request_id,))
                row = await cursor.fetchone()

        if row is None:
            return None

        return self._to_record(row)

    @override
    async def get_active_requests(
        self,
    ) -> list[TicketRequestRecord]:
        query = """
            SELECT
                id,
                departure_station,
                arrival_station,
                travel_date,
                travel_time,
                chat_id,
                user_id,
                user_name,
                is_active,
                created_at,
                updated_at
            FROM ticket_requests
            WHERE is_active = TRUE
            ORDER BY created_at
        """

        async with self._database.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query)
                rows = await cursor.fetchall()

        return [self._to_record(row) for row in rows]

    @override
    async def get_active_requests_by_chat(
        self,
        chat_id: int,
    ) -> list[TicketRequestRecord]:
        query = """
            SELECT
                id,
                departure_station,
                arrival_station,
                travel_date,
                travel_time,
                chat_id,
                user_id,
                user_name,
                is_active,
                created_at,
                updated_at
            FROM ticket_requests
            WHERE chat_id = %s
              AND is_active = TRUE
            ORDER BY created_at
        """

        async with self._database.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (chat_id,))
                rows = await cursor.fetchall()

        return [self._to_record(row) for row in rows]

    @override
    async def get_chats_by_request(
        self,
        request: TicketRequest,
    ) -> list[int]:
        query = """
            SELECT DISTINCT chat_id
            FROM ticket_requests
            WHERE departure_station = %s
              AND arrival_station = %s
              AND travel_date = %s
              AND travel_time = %s
              AND is_active = TRUE
        """

        async with self._database.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        request.departure_station,
                        request.arrival_station,
                        request.travel_date,
                        request.travel_time,
                    ),
                )

                rows = await cursor.fetchall()

        return [row[0] for row in rows]

    @override
    async def deactivate_request(
        self,
        request: TicketRequest,
        chat_id: int,
    ) -> None:
        query = """
            UPDATE ticket_requests
            SET
                is_active = FALSE,
                updated_at = NOW()
            WHERE departure_station = %s
              AND arrival_station = %s
              AND travel_date = %s
              AND travel_time = %s
              AND chat_id = %s
              AND is_active = TRUE
        """

        async with self._database.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    query,
                    (
                        request.departure_station,
                        request.arrival_station,
                        request.travel_date,
                        request.travel_time,
                        chat_id,
                    ),
                )

    @override
    async def deactivate_requests_by_chat(
        self,
        chat_id: int,
    ) -> int:
        query = """
            UPDATE ticket_requests
            SET
                is_active = FALSE,
                updated_at = NOW()
            WHERE chat_id = %s
              AND is_active = TRUE
        """

        async with self._database.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, (chat_id,))
                return cursor.rowcount

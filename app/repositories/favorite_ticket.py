import logging
from datetime import time
from typing import override

from psycopg.rows import dict_row

from app.database import PostgresDatabase
from app.interfaces import IFavoriteTicketRepository
from app.schemas import FavoriteTicket


class PostgresFavoriteTicketRepository(IFavoriteTicketRepository):
    def __init__(
        self,
        database: PostgresDatabase,
        max_favorites: int,
    ) -> None:
        self._database = database
        self._max_favorites = max_favorites

        self._logger = logging.getLogger(__name__)

    @override
    async def add_favorite(
        self,
        ticket: FavoriteTicket,
        user_id: int,
    ) -> None:
        insert_query = """
            INSERT INTO favorite_tickets (
                departure_station,
                arrival_station,
                travel_time,
                user_id
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """

        cleanup_query = """
            DELETE FROM favorite_tickets
            WHERE id IN (
                SELECT id
                FROM favorite_tickets
                WHERE user_id = %s
                ORDER BY created_at DESC
                OFFSET %s
            )
        """

        async with self._database.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    insert_query,
                    (
                        ticket.departure_station,
                        ticket.arrival_station,
                        ticket.travel_time,
                        user_id,
                    ),
                )

                await cursor.execute(
                    cleanup_query,
                    (
                        user_id,
                        self._max_favorites,
                    ),
                )

        self._logger.debug(
            "Favorite ticket saved: user_id=%s, %s -> %s",
            user_id,
            ticket.departure_station,
            ticket.arrival_station,
        )

    @override
    async def get_favorites(
        self,
        user_id: int,
    ) -> list[FavoriteTicket]:
        query = """
            SELECT
                departure_station,
                arrival_station,
                travel_time
            FROM favorite_tickets
            WHERE user_id = %s
            ORDER BY created_at DESC
        """

        async with self._database.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, (user_id,))
                rows = await cursor.fetchall()

        tickets: list[FavoriteTicket] = []

        for row in rows:
            travel_time = row["travel_time"]

            if isinstance(travel_time, time):
                travel_time = travel_time.strftime("%H:%M")

            tickets.append(
                FavoriteTicket(
                    departure_station=row["departure_station"],
                    arrival_station=row["arrival_station"],
                    travel_time=travel_time,
                )
            )

        return tickets

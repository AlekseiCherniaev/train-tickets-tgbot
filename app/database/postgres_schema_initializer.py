import logging

from app.database.postgres_database import PostgresDatabase


class PostgresSchemaInitializer:
    def __init__(self, database: PostgresDatabase) -> None:
        self._database = database
        self._logger = logging.getLogger(__name__)

    async def initialize(self) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ticket_requests (
                    id SERIAL PRIMARY KEY,
                    departure_station VARCHAR(100) NOT NULL,
                    arrival_station VARCHAR(100) NOT NULL,
                    travel_date DATE NOT NULL,
                    travel_time TIME NOT NULL,
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    user_name VARCHAR(200),
                    is_active BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )

            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS favorite_tickets (
                    id SERIAL PRIMARY KEY,
                    departure_station VARCHAR(100) NOT NULL,
                    arrival_station VARCHAR(100) NOT NULL,
                    travel_time TIME NOT NULL,
                    user_id BIGINT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )

            await connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_ticket_requests_active_unique
                ON ticket_requests (
                    departure_station,
                    arrival_station,
                    travel_date,
                    travel_time,
                    chat_id
                )
                WHERE is_active = TRUE
                """
            )

            await connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_favorite_tickets_unique
                ON favorite_tickets (
                    departure_station,
                    arrival_station,
                    travel_time,
                    user_id
                )
                """
            )

        self._logger.info("Postgres schema initialized")

import structlog
from psycopg2 import sql

from app.db.database_connection import PostgresDatabaseConnection
from app.settings import settings

logger = structlog.get_logger(__name__)


class TicketRequestRepository:
    def __init__(self, db_connection: PostgresDatabaseConnection) -> None:
        self._db = db_connection
        self._db.connect()

    def create_table(self) -> None:
        with self._db.connection.cursor() as cursor:
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS ticket_requests
                           (
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
                           """)
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS favorite_tickets
                           (
                               id SERIAL PRIMARY KEY,
                               departure_station VARCHAR(100) NOT NULL,
                               arrival_station VARCHAR(100) NOT NULL,
                               travel_time TIME NOT NULL,
                               user_id BIGINT NOT NULL,
                               created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                               )
                           """)
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_ticket_requests_active_unique
                    ON ticket_requests (departure_station, arrival_station, travel_date, travel_time, chat_id)
                    WHERE is_active = TRUE
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_favorite_tickets_unique
                    ON favorite_tickets (departure_station, arrival_station, travel_time, user_id)
                """
            )
            self._db.connection.commit()
            logger.info(
                "Table ticket_requests created successfully in database %s",
                self._db.connection.dsn,
            )

    def add_request(
        self,
        departure: str,
        arrival: str,
        date: str,
        time: str,
        chat_id: int,
        user_id: int,
        user_name: str,
    ) -> int | None:
        query = sql.SQL(
            """
            INSERT INTO ticket_requests
            (departure_station,
             arrival_station,
             travel_date,
             travel_time,
             chat_id,
             user_id,
             user_name,
             is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (departure_station, arrival_station, travel_date, travel_time, chat_id)
            WHERE is_active = TRUE
            DO UPDATE SET updated_at = NOW()
            RETURNING id
            """
        )

        with self._db.connection.cursor() as cursor:
            cursor.execute(
                query, (departure, arrival, date, time, chat_id, user_id, user_name)
            )
            row = cursor.fetchone()
            self._db.connection.commit()

            request_id = int(row[0]) if row else None
            logger.debug(
                "Request saved (id=%s): %s -> %s %s %s chat_id=%s user_id=%s",
                request_id,
                departure,
                arrival,
                date,
                time,
                chat_id,
                user_id,
            )
            return request_id

    def get_request_by_id(self, request_id: int) -> dict | None:
        query = sql.SQL(
            """
            SELECT id,
                   departure_station,
                   arrival_station,
                   travel_date,
                   travel_time,
                   chat_id,
                   user_id,
                   user_name,
                   is_active
            FROM ticket_requests
            WHERE id = %s
            """
        )
        with self._db.connection.cursor() as cursor:
            cursor.execute(query, (request_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return dict(row)

    def get_active_requests(self) -> list[dict]:
        query = sql.SQL("""SELECT id,
                                  departure_station,
                                  arrival_station,
                                  travel_date,
                                  travel_time,
                                  chat_id,
                                  user_id,
                                  user_name
                           FROM ticket_requests
                           WHERE is_active = TRUE""")
        with self._db.connection.cursor() as cursor:
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def get_active_requests_by_chat_id(self, chat_id: int) -> list[dict]:
        query = sql.SQL("""SELECT id,
                                  departure_station,
                                  arrival_station,
                                  travel_date,
                                  travel_time,
                                  created_at
                           FROM ticket_requests
                           WHERE chat_id = %s AND is_active = TRUE
                        """)
        with self._db.connection.cursor() as cursor:
            cursor.execute(query, (chat_id,))
            return [dict(row) for row in cursor.fetchall()]

    def set_request_inactive(
        self,
        departure: str,
        arrival: str,
        date: str,
        time: str,
        chat_id: int,
    ) -> None:
        query = sql.SQL("""
                        UPDATE ticket_requests
                        SET is_active = FALSE, updated_at = NOW()
                        WHERE departure_station = %s AND arrival_station = %s AND travel_date = %s AND travel_time = %s AND chat_id = %s
                        """)
        with self._db.connection.cursor() as cursor:
            cursor.execute(query, (departure, arrival, date, time, chat_id))
            self._db.connection.commit()
            logger.debug(
                f"Request: Departure {departure} Arrival {arrival} Date {date} Time {time} set inactive successfully"
            )

    def set_requests_inactive_by_chat_id(self, chat_id: int) -> int:
        query = sql.SQL("""
                        UPDATE ticket_requests
                        SET is_active = FALSE,
                            updated_at = NOW()
                        WHERE chat_id = %s AND is_active = TRUE
                        """)
        with self._db.connection.cursor() as cursor:
            cursor.execute(query, (chat_id,))
            updated_rows = cursor.rowcount
            self._db.connection.commit()
            logger.debug(f"Updated {updated_rows} requests for chat_id {chat_id}")
            return updated_rows

    def get_chats_by_ticket_params(
        self, departure: str, arrival: str, date: str, time: str
    ) -> list[int]:
        query = sql.SQL("""
                        SELECT DISTINCT chat_id
                        FROM ticket_requests
                        WHERE departure_station = %s AND arrival_station = %s AND travel_date = %s AND travel_time = %s AND is_active = TRUE
                        """)
        with self._db.connection.cursor() as cursor:
            cursor.execute(query, (departure, arrival, date, time))
            result = cursor.fetchall()
            return [row[0] for row in result]

    def add_favorite_ticket(
        self, departure: str, arrival: str, travel_time: str, user_id: int
    ) -> None:
        query = sql.SQL(
            """
            INSERT INTO favorite_tickets
            (departure_station,
             arrival_station,
             travel_time,
             user_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """
        )
        with self._db.connection.cursor() as cursor:
            cursor.execute(query, (departure, arrival, travel_time, user_id))

            query = sql.SQL(
                """
                SELECT id
                FROM favorite_tickets
                WHERE user_id = %s
                ORDER BY created_at DESC
                """
            )
            cursor.execute(query, (user_id,))
            fav_ticket_ids = [row[0] for row in cursor.fetchall()]

            if len(fav_ticket_ids) > settings.favorite_tickets_amount:
                delete_ids = fav_ticket_ids[settings.favorite_tickets_amount :]
                cursor.execute(
                    sql.SQL("DELETE FROM favorite_tickets WHERE id = ANY(%s)"),
                    (delete_ids,),
                )

            self._db.connection.commit()
            logger.debug("Favorite ticket added successfully")

    def get_favorite_tickets(self, user_id: int) -> list[dict]:
        query = sql.SQL("""SELECT departure_station,
                                  arrival_station,
                                  travel_time
                           FROM favorite_tickets
                           WHERE user_id = %s
                        """)
        with self._db.connection.cursor() as cursor:
            cursor.execute(query, (user_id,))
            return [dict(row) for row in cursor.fetchall()]

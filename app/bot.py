import asyncio
import logging
from urllib.parse import urlencode

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.database.postgres_database import PostgresDatabase
from app.database.postgres_schema_initializer import PostgresSchemaInitializer
from app.handlers import (
    FAVORITE_CALLBACK_PREFIX,
    TicketHandlers,
    get_reply_markup,
)
from app.http_session import HttpSession
from app.interfaces import IRWClient, ITicketRepository, IRWBrowserService
from app.messages import (
    ANOTHER_TICKET_BUTTON,
    CANCEL_BUTTON,
    FAVORITE_TICKETS_BUTTON,
    SEE_ALL_TICKETS_BUTTON,
    SEE_AVAILABLE_TICKETS_BUTTON,
    target_block_not_found_error_message,
    tickets_found_message,
)
from app.schemas import (
    TicketAvailabilityStatus,
    TicketRequest,
)
from app.settings import Settings, ProxySettings
from app.utils import calculate_retry_time

logger = logging.getLogger(__name__)


class TicketBot:
    def __init__(
        self,
        settings: Settings,
        proxy_settings: ProxySettings,
        handlers: TicketHandlers,
        rw_client: IRWClient,
        ticket_repository: ITicketRepository,
        database: PostgresDatabase,
        schema_initializer: PostgresSchemaInitializer,
        browser: IRWBrowserService,
        http_session: HttpSession,
    ) -> None:
        self._settings = settings
        self._proxy_settings = proxy_settings
        self._handlers = handlers
        self._rw_client = rw_client
        self._ticket_repository = ticket_repository

        self._database = database
        self._schema_initializer = schema_initializer
        self._browser = browser
        self._http_session = http_session

        self._application: Application | None = None
        self._background_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        proxy_url = (
            f"http://{self._proxy_settings.login}:"
            f"{self._proxy_settings.password}@"
            f"{self._proxy_settings.host}:"
            f"{self._proxy_settings.port}"
        )

        self._application = (
            ApplicationBuilder()
            .token(self._settings.bot_token)
            .proxy(proxy_url)
            .get_updates_proxy(proxy_url)
            .connect_timeout(5)
            .get_updates_connect_timeout(5)
            .post_init(self._post_init)
            .post_stop(self._post_stop)
            .build()
        )

        self._add_handlers()

        logger.info("Starting bot")

        self._application.run_polling(
            allowed_updates=Update.ALL_TYPES,
        )

    async def _post_init(
        self,
        application: Application,
    ) -> None:
        await self._database.start()
        await self._schema_initializer.initialize()
        await self._http_session.start()

        self._background_task = asyncio.create_task(self._check_ticket_availability(application))

        logger.info("Application resources started")

    async def _post_stop(
        self,
        application: Application,
    ) -> None:
        if self._background_task is not None:
            self._background_task.cancel()

            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

            self._background_task = None

        await self._browser.stop()
        await self._http_session.stop()
        await self._database.stop()

        logger.info("Application resources stopped")

    async def _check_ticket_availability(
        self,
        application: Application,
    ) -> None:
        while True:
            await asyncio.sleep(
                calculate_retry_time(
                    self._settings.retry_time,
                )
            )

            try:
                await self._check_active_requests(application)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Ticket checking failed")

    async def _check_active_requests(
        self,
        application: Application,
    ) -> None:
        records = await self._ticket_repository.get_active_requests()

        unique_requests: dict[
            tuple[str, str, str, str],
            TicketRequest,
        ] = {}

        for record in records:
            ticket = TicketRequest(
                departure_station=record.departure_station,
                arrival_station=record.arrival_station,
                travel_date=record.travel_date,
                travel_time=record.travel_time,
            )

            key = (
                ticket.departure_station,
                ticket.arrival_station,
                ticket.travel_date,
                ticket.travel_time,
            )

            unique_requests[key] = ticket

        for ticket in unique_requests.values():
            await asyncio.sleep(
                calculate_retry_time(
                    self._settings.request_delay,
                )
            )

            try:
                await self._check_ticket(
                    ticket,
                    application,
                )
            except Exception:
                logger.exception(
                    "Failed checking ticket %s -> %s %s %s",
                    ticket.departure_station,
                    ticket.arrival_station,
                    ticket.travel_date,
                    ticket.travel_time,
                )

    async def _check_ticket(
        self,
        ticket: TicketRequest,
        application: Application,
    ) -> None:
        status = await self._rw_client.check_availability(ticket)

        match status:
            case TicketAvailabilityStatus.INVALID:
                await self._handle_invalid_ticket(
                    ticket,
                    application,
                )

            case TicketAvailabilityStatus.UNAVAILABLE:
                logger.debug(
                    "No tickets available: %s",
                    ticket,
                )

            case TicketAvailabilityStatus.AVAILABLE:
                await self._handle_available_ticket(
                    ticket,
                    application,
                )

    async def _handle_invalid_ticket(
        self,
        ticket: TicketRequest,
        application: Application,
    ) -> None:
        chat_ids = await self._ticket_repository.get_chats_by_request(
            ticket,
        )

        for chat_id in chat_ids:
            try:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=target_block_not_found_error_message.format(
                        ticket.departure_station,
                        ticket.arrival_station,
                    ),
                    reply_markup=get_reply_markup(),
                )
            except Exception:
                logger.exception(
                    "Failed to notify chat_id=%s about invalid ticket",
                    chat_id,
                )
            finally:
                await self._ticket_repository.deactivate_request(
                    ticket,
                    chat_id,
                )

        logger.debug(
            "Ticket request became invalid: %s",
            ticket,
        )

    async def _handle_available_ticket(
        self,
        ticket: TicketRequest,
        application: Application,
    ) -> None:
        chat_ids = await self._ticket_repository.get_chats_by_request(
            ticket,
        )

        query = urlencode(
            {
                "from": ticket.departure_station,
                "to": ticket.arrival_station,
                "date": ticket.travel_date,
            }
        )

        url = f"https://pass.rw.by/ru/route/?{query}"

        for chat_id in chat_ids:
            try:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=tickets_found_message.format(
                        ticket.departure_station,
                        ticket.arrival_station,
                        ticket.travel_date,
                        ticket.travel_time,
                        url,
                    ),
                    reply_markup=get_reply_markup(),
                )
            except Exception:
                logger.exception(
                    "Failed to notify chat_id=%s about available ticket",
                    chat_id,
                )

        logger.info(
            "Tickets found: %s -> %s %s %s",
            ticket.departure_station,
            ticket.arrival_station,
            ticket.travel_date,
            ticket.travel_time,
        )

    def _add_handlers(self) -> None:
        if self._application is None:
            raise RuntimeError("Application is not initialized")

        cancel_filter = filters.Regex(CANCEL_BUTTON)
        add_ticket_filter = filters.Regex(ANOTHER_TICKET_BUTTON)
        see_all_filter = filters.Regex(SEE_ALL_TICKETS_BUTTON)
        favorite_filter = filters.Regex(FAVORITE_TICKETS_BUTTON)
        see_available_filter = filters.Regex(
            SEE_AVAILABLE_TICKETS_BUTTON,
        )

        see_available_input = filters.Regex(r"^\S+\s+\S+\s+\d{4}-\d{2}-\d{2}$")

        text_filter = (
            filters.TEXT
            & ~filters.COMMAND
            & ~cancel_filter
            & ~see_all_filter
            & ~favorite_filter
            & ~add_ticket_filter
            & ~see_available_filter
            & ~see_available_input
        )

        telegram_handlers = [
            CommandHandler(
                "start",
                self._handlers.start,
            ),
            CallbackQueryHandler(
                self._handlers.add_favorite_ticket,
                pattern=f"^{FAVORITE_CALLBACK_PREFIX}",
            ),
            MessageHandler(
                cancel_filter,
                self._handlers.cancel,
            ),
            MessageHandler(
                see_all_filter,
                self._handlers.see_active_tickets,
            ),
            MessageHandler(
                favorite_filter,
                self._handlers.get_favorite_tickets,
            ),
            MessageHandler(
                add_ticket_filter,
                self._handlers.add_another_ticket,
            ),
            MessageHandler(
                see_available_filter,
                self._handlers.see_available_tickets_info,
            ),
            MessageHandler(
                see_available_input,
                self._handlers.see_available_tickets,
            ),
            MessageHandler(
                text_filter,
                self._handlers.enter_ticket,
            ),
        ]

        for handler in telegram_handlers:
            self._application.add_handler(handler)

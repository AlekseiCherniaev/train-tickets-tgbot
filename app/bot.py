import asyncio

import aiohttp
import structlog
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    Application,
    CallbackQueryHandler,
)

from app.browser_service import BrowserService
from app.db.database_connection import PostgresDatabaseConnection
from app.db.ticket_request_repo import TicketRequestRepository
from app.handlers import (
    enter_ticket_handler,
    cancel_handler,
    add_another_ticket_handler,
    start_handler,
    get_reply_markup,
    see_active_tickets_handler,
    get_favorite_tickets_handler,
    add_favorite_ticket_handler,
    FAVORITE_CALLBACK_PREFIX,
    see_available_tickets,
    see_available_tickets_info,
)
from app.messages import (
    ANOTHER_TICKET_BUTTON,
    CANCEL_BUTTON,
    target_block_not_found_error_message,
    tickets_found_message,
    SEE_ALL_TICKETS_BUTTON,
    FAVORITE_TICKETS_BUTTON,
    SEE_AVAILABLE_TICKETS_BUTTON,
)
from app.settings import settings
from app.ticket_parser import TicketParser
from app.utils import make_get_request, calculate_retry_time

logger = structlog.get_logger(__name__)


class TicketBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.application: Application | None = None  # type: ignore
        self.ticket_repo = TicketRequestRepository(
            PostgresDatabaseConnection(
                dbname=settings.postgres_db,
                dbuser=settings.postgres_user,
                dbpassword=settings.postgres_password,
                dbhost=settings.postgres_host,
                dbport=settings.postgres_port,
            )
        )

    def start_bot(self) -> None:
        """Main entry point for starting the bot."""
        logger.info("Starting bot...")
        self.ticket_repo.create_table()
        self.application = (
            ApplicationBuilder()
            .token(self.token)
            .post_init(self.background_task)
            .post_stop(self.shutdown)
            .build()
        )
        self.application.bot_data["ticket_repo"] = self.ticket_repo
        self.add_handlers()

        logger.info("Startup complete")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    @staticmethod
    async def background_task(application: Application) -> None:  # type: ignore
        asyncio.create_task(TicketBot.check_ticket_availability(application))

    @staticmethod
    async def _send_error_message(request_data, application):
        active_chats = application.bot_data["ticket_repo"].get_chats_by_ticket_params(
            departure=request_data[0],
            arrival=request_data[1],
            date=request_data[2],
            time=request_data[3],
        )
        for chat_id in active_chats:
            await application.bot.send_message(
                chat_id=chat_id,
                text=target_block_not_found_error_message.format(
                    request_data[0], request_data[1]
                ),
                reply_markup=get_reply_markup(),
            )
            application.bot_data["ticket_repo"].set_request_inactive(
                departure=request_data[0],
                arrival=request_data[1],
                date=request_data[2],
                time=request_data[3],
                chat_id=chat_id,
            )
        logger.bind(params=request_data).debug("Target block not found")

    @staticmethod
    async def check_ticket_availability(application: Application) -> None:  # type: ignore
        while True:
            await asyncio.sleep(calculate_retry_time())
            logger.info("Checking ticket availability...")
            unique_requests = {
                (
                    request["departure_station"],
                    request["arrival_station"],
                    request["travel_date"],
                    request["travel_time"],
                )
                for request in application.bot_data["ticket_repo"].get_active_requests()
            }

            async with aiohttp.ClientSession() as session:
                try:
                    for request_data in unique_requests:
                        await asyncio.sleep(calculate_retry_time(0.66))
                        response = await make_get_request(
                            params=request_data, session=session
                        )
                        if response.status != 200:
                            raise Exception(f"HTTP error {response.status}")

                        ticket_parser = TicketParser(response=await response.text())
                        requested_time_str = str(request_data[3].strftime("%H:%M"))
                        train_block = ticket_parser.get_train_block(
                            train_time=requested_time_str
                        )
                        if not train_block:
                            await TicketBot._send_error_message(
                                request_data=request_data, application=application
                            )
                            continue

                        is_available = ticket_parser.check_ticket_availability(
                            train_block=train_block
                        )
                        if not is_available:
                            logger.bind(params=request_data).debug("No tickets found")
                            continue

                        has_only_disabled_places = (
                            await BrowserService().has_only_disabled_places(
                                from_station=request_data[0],
                                to_station=request_data[1],
                                date=str(request_data[2]),
                                train_time=requested_time_str,
                            )
                        )
                        if has_only_disabled_places:
                            logger.bind(params=request_data).debug(
                                "Tickets found, but places only for disabled"
                            )
                            continue

                        active_chats = application.bot_data[
                            "ticket_repo"
                        ].get_chats_by_ticket_params(
                            departure=request_data[0],
                            arrival=request_data[1],
                            date=request_data[2],
                            time=request_data[3],
                        )
                        url = f"https://pass.rw.by/ru/route/?from={request_data[0]}&to={request_data[1]}&date={request_data[2]}"
                        for chat_id in active_chats:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=tickets_found_message.format(
                                    request_data[0],
                                    request_data[1],
                                    request_data[2],
                                    request_data[3],
                                    url,
                                ),
                                reply_markup=get_reply_markup(),
                            )
                        logger.bind(params=request_data).debug("Tickets found")

                except Exception as e:
                    logger.bind(error=str(e)).error("Ticket checking error")
                    await asyncio.sleep(calculate_retry_time(1))

    def add_handlers(self) -> None:
        """Register all handlers with the application."""
        if not self.application:
            raise ValueError("Application not initialized. Call start_bot() first.")

        CANCEL_KEYWORDS = filters.Regex(CANCEL_BUTTON)
        ADD_TICKET_KEYWORDS = filters.Regex(ANOTHER_TICKET_BUTTON)
        SEE_ALL_TICKETS = filters.Regex(SEE_ALL_TICKETS_BUTTON)
        FAVORITE_TICKETS = filters.Regex(FAVORITE_TICKETS_BUTTON)
        SEE_AVAILABLE_TICKETS = filters.Regex(SEE_AVAILABLE_TICKETS_BUTTON)

        SEE_AVAILABLE_TICKETS_INPUT = filters.Regex(r"^\S+\s+\S+\s+\d{4}-\d{2}-\d{2}$")

        TEXT_FILTER = (
            filters.TEXT
            & ~filters.COMMAND
            & ~CANCEL_KEYWORDS
            & ~SEE_ALL_TICKETS
            & ~FAVORITE_TICKETS
            & ~ADD_TICKET_KEYWORDS
            & ~SEE_AVAILABLE_TICKETS
            & ~SEE_AVAILABLE_TICKETS_INPUT
        )
        handlers = [
            CommandHandler("start", start_handler),
            CallbackQueryHandler(
                add_favorite_ticket_handler, pattern=f"^{FAVORITE_CALLBACK_PREFIX}"
            ),
            MessageHandler(SEE_AVAILABLE_TICKETS_INPUT, see_available_tickets),
            MessageHandler(SEE_AVAILABLE_TICKETS, see_available_tickets_info),
            MessageHandler(TEXT_FILTER, enter_ticket_handler),
            MessageHandler(CANCEL_KEYWORDS, cancel_handler),
            MessageHandler(SEE_ALL_TICKETS, see_active_tickets_handler),
            MessageHandler(FAVORITE_TICKETS, get_favorite_tickets_handler),
            MessageHandler(ADD_TICKET_KEYWORDS, add_another_ticket_handler),
        ]
        for handler in handlers:
            self.application.add_handler(handler)

        logger.info("All handlers added")

    @staticmethod
    async def shutdown(application: Application) -> None:
        await BrowserService.close()
        logger.info("Shutdown complete")

import aiohttp
import structlog
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from app.db.ticket_request_repo import TicketRequestRepository
from app.messages import (
    start_message,
    invalid_input_amount_message,
    invalid_time_format_message,
    error_finding_train_message,
    request_error_message,
    cancel_ticket_message,
    add_ticket_message,
    start_finding_tickets_message,
    CANCEL_TICKETS_TEXT,
    ADD_TICKET_TEXT,
    SEE_ALL_TICKETS_TEXT,
    see_all_tickets_message,
)
from app.ticket_parser import TicketParser
from app.utils import (
    make_get_request,
    validate_time_input,
    get_example_routes_str,
    format_created_at_minsk,
)

logger = structlog.get_logger(__name__)


def get_reply_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[CANCEL_TICKETS_TEXT], [ADD_TICKET_TEXT], [SEE_ALL_TICKETS_TEXT]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Введите маршрут: Откуда Куда Дата Время",
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        f"{start_message}{get_example_routes_str()}", reply_markup=get_reply_markup()
    )
    logger.bind(
        user_id=update.effective_user.id,
        username=update.effective_user.username,
        chat_id=update.message.chat_id,
    ).info(f"User {update.effective_user.id} started bot")


async def enter_ticket_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Process user input for ticket search."""
    params = update.message.text.split()
    if len(params) != 4:
        await update.message.reply_html(
            f"{invalid_input_amount_message}{get_example_routes_str()}",
            reply_markup=get_reply_markup(),
        )
        logger.bind(params=update.message.text).debug("Wrong ticket params")  # type: ignore
        return None

    if not validate_time_input(
        date_str=params[2],
        time_str=params[3],
        chat_id=update.message.chat_id,
    ):
        await update.message.reply_html(  # type: ignore
            f"{invalid_time_format_message}{get_example_routes_str()}",
            reply_markup=get_reply_markup(),
        )
        logger.bind(
            date_str=params[2], time_str=params[3], chat_id=update.message.chat_id
        ).debug("Wrong date or time format")
        return None

    async with aiohttp.ClientSession() as session:
        try:
            response = await make_get_request(params=params, session=session)
            if response.status != 200:
                raise Exception(f"HTTP error {response.status}")

            ticket_parser = TicketParser(response=await response.text())
            if not ticket_parser.validate_rzd_response(params, update.message.chat_id):
                await update.message.reply_html(
                    f"{error_finding_train_message}{get_example_routes_str()}",
                    reply_markup=get_reply_markup(),
                )
                return None
            else:
                await update.message.reply_html(
                    start_finding_tickets_message.format(
                        params[0], params[1], params[2], params[3]
                    ),
                    reply_markup=get_reply_markup(),
                )

        except Exception as e:
            logger.bind(error=str(e), chat_id=update.message.chat_id).error(
                "Ticket checking error"
            )
            await update.message.reply_html(  # type: ignore
                request_error_message.format(params[0], params[1]),
                reply_markup=get_reply_markup(),
            )
            return None

    ticket_repo: TicketRequestRepository = context.bot_data["ticket_repo"]
    ticket_repo.add_request(
        departure=params[0],
        arrival=params[1],
        date=params[2],
        time=params[3],
        chat_id=update.message.chat_id,
        user_id=update.effective_user.id,
        user_name=update.effective_user.username,  # type: ignore
    )
    return None


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel active search tasks."""
    ticket_repo: TicketRequestRepository = context.bot_data["ticket_repo"]
    result = ticket_repo.set_requests_inactive_by_chat_id(
        chat_id=update.message.chat_id
    )
    await update.message.reply_html(
        f"{cancel_ticket_message.format(result)}{get_example_routes_str()}",
        reply_markup=get_reply_markup(),
    )
    logger.bind(
        user_id=update.effective_user.id,
        chat_id=update.message.chat_id,
    ).debug(f"User {update.effective_user.id} cancelled {result} tickets")


async def add_another_ticket_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle a request to add another ticket search."""
    await update.message.reply_html(
        f"{add_ticket_message}{get_example_routes_str()}",
        reply_markup=get_reply_markup(),
    )
    logger.bind(
        user_id=update.effective_user.id,
        chat_id=update.message.chat_id,
    ).debug(f"User {update.effective_user.id} add ticket")


async def see_active_tickets_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    ticket_repo: TicketRequestRepository = context.bot_data["ticket_repo"]
    active_tickets = ticket_repo.get_active_requests_by_chat_id(
        chat_id=update.message.chat_id
    )
    if not active_tickets:
        tickets_str = "Нет активных поисков"
    else:
        tickets_str = "".join(
            (
                f"{i}. {t['departure_station']} -> {t['arrival_station']}\n"
                f"{t['travel_date']} {str(t['travel_time'])[:5]}\n"
                f"Добавлен: {format_created_at_minsk(t['created_at'])}\n"
            )
            for i, t in enumerate(active_tickets, start=1)
        )
    await update.message.reply_html(
        f"{see_all_tickets_message}{tickets_str}",
        reply_markup=get_reply_markup(),
    )
    logger.bind(
        user_id=update.effective_user.id,
        chat_id=update.message.chat_id,
    ).debug(f"User {update.effective_user.id} see all tickets")

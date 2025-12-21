import aiohttp
import structlog
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
    favorite_tickets_message,
    FAVORITE_TICKETS_TEXT,
    ADD_FAVORITE_TICKET_TEXT,
)
from app.ticket_parser import TicketParser
from app.utils import (
    make_get_request,
    validate_time_input,
    get_example_routes_str,
    format_created_at_minsk,
    get_minsk_date,
)

logger = structlog.get_logger(__name__)

FAVORITE_CALLBACK_PREFIX = "favorite_route:"


def _make_favorite_callback_data(request_id: int) -> str:
    return f"{FAVORITE_CALLBACK_PREFIX}{request_id}"


def make_add_favorite_inline_markup(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=ADD_FAVORITE_TICKET_TEXT,
                    callback_data=_make_favorite_callback_data(request_id),
                )
            ]
        ]
    )


def get_reply_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [ADD_TICKET_TEXT, SEE_ALL_TICKETS_TEXT],
            [CANCEL_TICKETS_TEXT, FAVORITE_TICKETS_TEXT],
        ],
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
    request_id = ticket_repo.add_request(
        departure=params[0],
        arrival=params[1],
        date=params[2],
        time=params[3],
        chat_id=update.message.chat_id,
        user_id=update.effective_user.id,
        user_name=update.effective_user.username,  # type: ignore
    )

    await update.message.reply_html(
        start_finding_tickets_message.format(
            params[0], params[1], params[2], params[3]
        ),
        reply_markup=(
            make_add_favorite_inline_markup(request_id)
            if request_id is not None
            else None
        ),
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


async def add_favorite_ticket_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.callback_query is None:
        return None

    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith(FAVORITE_CALLBACK_PREFIX):
        return None

    request_id = int(data.removeprefix(FAVORITE_CALLBACK_PREFIX))
    ticket_repo: TicketRequestRepository = context.bot_data["ticket_repo"]
    ticket_request = ticket_repo.get_request_by_id(request_id=request_id)
    ticket_repo.add_favorite_ticket(
        departure=ticket_request["departure_station"],
        arrival=ticket_request["arrival_station"],
        travel_time=str(ticket_request["travel_time"])[:5],
        user_id=update.effective_user.id,
    )

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_html(  # type: ignore[union-attr]
        "📍 Маршрут добавлен в избранные",
        reply_markup=get_reply_markup(),
    )
    return None


async def get_favorite_tickets_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    ticket_repo: TicketRequestRepository = context.bot_data["ticket_repo"]
    fav_tickets = ticket_repo.get_favorite_tickets(user_id=update.effective_user.id)
    if not fav_tickets:
        fav_tickets_str = (
            "Нет избранных маршрутов\n"
            "Чтобы добавить, начните поиск и \n"
            "нажмите на кнопку '⭐️ Добавить маршрут в избранные'"
        )
    else:
        fav_tickets_str = "".join(
            (
                f"<code>{t['departure_station']} {t['arrival_station']} {str(get_minsk_date())[:-2]}__ {str(t['travel_time'])[:5]}</code>\n\n"
            )
            for t in fav_tickets
        )
    await update.message.reply_html(
        f"{favorite_tickets_message}{fav_tickets_str}",
        reply_markup=get_reply_markup(),
    )
    logger.bind(
        user_id=update.effective_user.id,
        chat_id=update.message.chat_id,
    ).debug(f"User {update.effective_user.id} see favorite tickets")

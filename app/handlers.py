import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes
from app.exceptions import InvalidRouteError
from app.interfaces import (
    IFavoriteTicketRepository,
    IRWClient,
    ITicketRepository,
)
from app.messages import (
    ADD_FAVORITE_TICKET_TEXT,
    ADD_TICKET_TEXT,
    CANCEL_TICKETS_TEXT,
    FAVORITE_TICKETS_TEXT,
    SEE_ALL_TICKETS_TEXT,
    SEE_AVAILABLE_TICKETS_TEXT,
    add_ticket_message,
    cancel_ticket_message,
    error_finding_train_message,
    favorite_tickets_message,
    invalid_input_amount_message,
    invalid_time_format_message,
    request_error_message,
    see_all_tickets_message,
    see_available_tickets_message,
    start_finding_tickets_message,
    start_message,
)
from app.schemas import (
    FavoriteTicket,
    NewTicketRequest,
    ScheduleRequest,
    TicketRequest,
)
from app.utils import (
    format_created_at_minsk,
    get_example_routes_str,
    get_minsk_date,
    validate_time_input,
    validate_date_input,
)

logger = logging.getLogger(__name__)

FAVORITE_CALLBACK_PREFIX = "favorite_route:"


def make_add_favorite_inline_markup(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=ADD_FAVORITE_TICKET_TEXT,
                    callback_data=f"{FAVORITE_CALLBACK_PREFIX}{request_id}",
                )
            ]
        ]
    )


def get_reply_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [SEE_AVAILABLE_TICKETS_TEXT],
            [ADD_TICKET_TEXT, SEE_ALL_TICKETS_TEXT],
            [CANCEL_TICKETS_TEXT, FAVORITE_TICKETS_TEXT],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Введите маршрут: Откуда Куда Дата Время",
    )


class TicketHandlers:
    def __init__(
        self,
        rw_client: IRWClient,
        ticket_repository: ITicketRepository,
        favorite_repository: IFavoriteTicketRepository,
    ) -> None:
        self._rw_client = rw_client
        self._ticket_repository = ticket_repository
        self._favorite_repository = favorite_repository
        self._date_format = "%Y-%m-%d"

    async def start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if update.message is None:
            return

        await update.message.reply_html(
            f"{start_message}{get_example_routes_str(self._date_format)}",
            reply_markup=get_reply_markup(),
        )

    async def enter_ticket(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        message = update.message
        user = update.effective_user

        if message is None or user is None or message.text is None:
            return

        params = message.text.split()

        if len(params) != 4:
            await message.reply_html(
                f"{invalid_input_amount_message}{get_example_routes_str(self._date_format)}",
                reply_markup=get_reply_markup(),
            )
            return

        departure_station, arrival_station, travel_date, travel_time = params

        if not validate_time_input(
            date_str=travel_date,
            time_str=travel_time,
            chat_id=message.chat_id,
            date_format=self._date_format,
        ):
            await message.reply_html(
                f"{invalid_time_format_message}{get_example_routes_str(self._date_format)}",
                reply_markup=get_reply_markup(),
            )
            return

        ticket = TicketRequest(
            departure_station=departure_station,
            arrival_station=arrival_station,
            travel_date=travel_date,
            travel_time=travel_time,
        )

        try:
            if not await self._rw_client.validate(ticket):
                await message.reply_html(
                    f"{error_finding_train_message}{get_example_routes_str(self._date_format)}",
                    reply_markup=get_reply_markup(),
                )
                return

        except Exception:
            logger.exception(
                "Ticket validation failed: %s -> %s",
                departure_station,
                arrival_station,
            )

            await message.reply_html(
                request_error_message.format(
                    departure_station,
                    arrival_station,
                ),
                reply_markup=get_reply_markup(),
            )
            return

        request = NewTicketRequest(
            departure_station=departure_station,
            arrival_station=arrival_station,
            travel_date=travel_date,
            travel_time=travel_time,
            chat_id=message.chat_id,
            user_id=user.id,
            user_name=user.username,
        )

        request_id = await self._ticket_repository.add_request(request)

        await message.reply_html(
            start_finding_tickets_message.format(
                departure_station,
                arrival_station,
                travel_date,
                travel_time,
            ),
            reply_markup=make_add_favorite_inline_markup(request_id),
        )

    async def cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        message = update.message

        if message is None:
            return

        deactivated_count = await self._ticket_repository.deactivate_requests_by_chat(
            message.chat_id,
        )

        await message.reply_html(
            f"{cancel_ticket_message.format(deactivated_count)}{get_example_routes_str(self._date_format)}",
            reply_markup=get_reply_markup(),
        )

    async def add_another_ticket(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if update.message is None:
            return

        await update.message.reply_html(
            f"{add_ticket_message}{get_example_routes_str(self._date_format)}",
            reply_markup=get_reply_markup(),
        )

    async def see_active_tickets(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        message = update.message

        if message is None:
            return

        tickets = await self._ticket_repository.get_active_requests_by_chat(
            message.chat_id,
        )

        if not tickets:
            tickets_text = "Нет активных поисков"
        else:
            tickets_text = "".join(
                (
                    f"{index}. "
                    f"{ticket.departure_station} -> "
                    f"{ticket.arrival_station}\n"
                    f"{ticket.travel_date} "
                    f"{ticket.travel_time}\n"
                    f"Добавлен: "
                    f"{format_created_at_minsk(ticket.created_at)}\n"
                )
                for index, ticket in enumerate(tickets, start=1)
            )

        await message.reply_html(
            f"{see_all_tickets_message}{tickets_text}",
            reply_markup=get_reply_markup(),
        )

    async def add_favorite_ticket(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        query = update.callback_query
        user = update.effective_user

        if query is None or user is None:
            return

        await query.answer()

        data = query.data or ""

        if not data.startswith(FAVORITE_CALLBACK_PREFIX):
            return

        try:
            request_id = int(
                data.removeprefix(FAVORITE_CALLBACK_PREFIX),
            )
        except ValueError:
            logger.warning("Invalid favorite request id: %s", data)
            return

        request = await self._ticket_repository.get_request_by_id(
            request_id,
        )

        if request is None:
            logger.warning(
                "Ticket request not found: id=%s",
                request_id,
            )
            return

        favorite = FavoriteTicket(
            departure_station=request.departure_station,
            arrival_station=request.arrival_station,
            travel_time=request.travel_time,
        )

        await self._favorite_repository.add_favorite(
            favorite,
            user.id,
        )

        await query.edit_message_reply_markup(reply_markup=None)

        if query.message is not None:
            await query.message.reply_html(
                "📍 Маршрут добавлен в избранные",
                reply_markup=get_reply_markup(),
            )

    async def get_favorite_tickets(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        message = update.message
        user = update.effective_user

        if message is None or user is None:
            return

        tickets = await self._favorite_repository.get_favorites(
            user.id,
        )

        if not tickets:
            tickets_text = (
                "Нет избранных маршрутов\n"
                "Чтобы добавить, начните поиск и \n"
                "нажмите на кнопку "
                "'⭐️ Добавить маршрут в избранные'"
            )
        else:
            date_template = get_minsk_date().strftime("%Y-%m-__")

            tickets_text = "".join(
                (
                    f"<code>"
                    f"{ticket.departure_station} "
                    f"{ticket.arrival_station} "
                    f"{date_template} "
                    f"{ticket.travel_time}"
                    f"</code>\n\n"
                )
                for ticket in tickets
            )

        await message.reply_html(
            f"{favorite_tickets_message}{tickets_text}",
            reply_markup=get_reply_markup(),
        )

    async def see_available_tickets_info(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if update.message is None:
            return

        await update.message.reply_html(
            see_available_tickets_message,
            reply_markup=get_reply_markup(),
        )

    async def see_available_tickets(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        message = update.message

        if message is None or message.text is None:
            return

        params = message.text.split()

        if len(params) != 3:
            await message.reply_html(
                "Нужен формат: <code>Откуда Куда ГГГГ-ММ-ДД</code>",
                reply_markup=get_reply_markup(),
            )
            return

        departure_station, arrival_station, travel_date = params

        if not validate_date_input(
            travel_date,
            self._date_format,
        ):
            await message.reply_html(
                "❌ Неверная дата. Используйте формат ГГГГ-ММ-ДД и укажите сегодняшнюю или будущую дату.",
                reply_markup=get_reply_markup(),
            )
            return

        request = ScheduleRequest(
            departure_station=departure_station,
            arrival_station=arrival_station,
            travel_date=travel_date,
        )

        try:
            trains = await self._rw_client.get_trains(request)

        except InvalidRouteError:
            await message.reply_html(
                "❌ Маршрут не найден. Проверьте названия станций.",
                reply_markup=get_reply_markup(),
            )
            return

        except Exception:
            logger.exception(
                "Failed to get trains: %s -> %s",
                departure_station,
                arrival_station,
            )

            await message.reply_html(
                "Ошибка при запросе доступных билетов. Попробуйте позже.",
                reply_markup=get_reply_markup(),
            )
            return

        if not trains:
            await message.reply_html(
                "Поездов на эту дату не найдено",
                reply_markup=get_reply_markup(),
            )
            return

        rows: list[str] = []

        for train in trains:
            time_range = train.departure_time

            if train.arrival_time:
                time_range = f"{train.departure_time}–{train.arrival_time}"

            if not train.is_selling_allowed:
                rows.append(f"• <b>{time_range}</b> — продажа онлайн недоступна")
                continue

            if not train.places or train.total_places <= 0:
                rows.append(f"• <b>{time_range}</b> — мест нет")
                continue

            details = "; ".join(f"{place.name}: <b>{place.amount}</b>" for place in train.places)

            rows.append(f"• <b>{time_range}</b> — <b>{train.total_places}</b> мест ({details})")

        await message.reply_html(
            "\n".join(
                [
                    f"<b>{departure_station} → {arrival_station}</b>",
                    f"<b>Дата:</b> {travel_date}",
                    *rows,
                ]
            ),
            reply_markup=get_reply_markup(),
            disable_web_page_preview=True,
        )

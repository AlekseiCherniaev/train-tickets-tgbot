import datetime
import logging
import random
import re
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)

MINSK_TZ = ZoneInfo("Europe/Minsk")


def format_created_at_minsk(value: datetime.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.UTC)

    return value.astimezone(MINSK_TZ).strftime("%H:%M %d-%m-%Y")

def validate_date_input(
    date_str: str,
    date_format: str,
) -> bool:
    try:
        input_date = datetime.datetime.strptime(
            date_str,
            date_format,
        ).date()
    except ValueError:
        return False

    return input_date >= get_minsk_date()


def get_minsk_date() -> datetime.date:
    return datetime.datetime.now(MINSK_TZ).date()


def get_example_routes_str(date_format: str) -> str:
    example_date = (get_minsk_date() + datetime.timedelta(days=1)).strftime(date_format)

    example1 = f"Толочин Минск-Пассажирский {example_date} 07:44"
    example2 = f"Минск-Пассажирский Пинск {example_date} 13:58"

    return f"<code>{example1}</code>\n<code>{example2}</code>\n"


def calculate_retry_time(base_delay: float) -> float:
    variation = base_delay * 0.25
    return random.uniform(
        base_delay - variation,
        base_delay + variation,
    )


def validate_time_input(
    date_str: str,
    time_str: str,
    chat_id: int,
    date_format: str,
) -> bool:
    logger.debug(
        "Validating time params: date=%s time=%s chat_id=%s",
        date_str,
        time_str,
        chat_id,
    )

    if not re.fullmatch(r"\d{2}:\d{2}", time_str):
        return False

    try:
        input_time = datetime.time.fromisoformat(time_str)
        input_date = datetime.datetime.strptime(
            date_str,
            date_format,
        ).date()
    except ValueError:
        return False

    now = datetime.datetime.now(MINSK_TZ)

    if input_date < now.date():
        return False

    if input_date == now.date() and input_time < now.time():
        return False

    return True

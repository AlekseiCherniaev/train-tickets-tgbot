import asyncio
import datetime
import random
import re
from zoneinfo import ZoneInfo

import aiohttp
import structlog
from aiohttp import ClientSession, ClientResponse
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.settings import settings

logger = structlog.get_logger(__name__)


def get_minsk_date() -> datetime.date:
    return (datetime.datetime.now(ZoneInfo("Europe/Minsk"))).date()


def get_example_routes_str():
    example1 = f"Толочин Минск-Пассажирский {get_minsk_date().strftime(settings.date_format)} 07:44"
    example2 = f"Минск-Пассажирский Пинск {get_minsk_date().strftime(settings.date_format)} 13:58"
    return f"<code>{example1}</code>\n<code>{example2}</code>\n"


def get_proxy_url() -> str:
    return f"http://{settings.proxy_login}:{settings.proxy_password}@{settings.proxy_host}:{settings.proxy_port}"


@retry(
    stop=stop_after_attempt(settings.retry_attempts),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    reraise=True,
)
async def make_get_request(
    params: tuple | list, session: ClientSession
) -> ClientResponse:
    url = (
        f"https://pass.rw.by/ru/route/?from={params[0]}&to={params[1]}&date={params[2]}"
    )
    try:
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)
        kwargs = {"headers": settings.headers, "timeout": timeout}
        if settings.use_proxy:
            kwargs["proxy"] = get_proxy_url()
            logger.bind(url=url).debug("Making request with proxy...")
        else:
            logger.bind(url=url).debug("Making request without proxy...")
        return await session.get(url, **kwargs)  # type: ignore
    except Exception as e:
        logger.bind(url=url).error(f"Request failed: {e}", exception=e)
        raise e


def calculate_retry_time(base_delay: float = settings.retry_time) -> float:
    variation = base_delay * 0.25
    return random.uniform(base_delay - variation, base_delay + variation)


def validate_time_input(date_str: str, time_str: str, chat_id: int) -> bool:
    """Validate if the input time is in the future."""
    logger.bind(date_str=date_str, time_str=time_str, chat_id=chat_id).debug(
        "Validating time params..."
    )
    if not re.fullmatch(r"\d{2}:\d{2}", time_str):
        return False

    try:
        input_time = datetime.time.fromisoformat(time_str)
        input_date = datetime.datetime.strptime(date_str, settings.date_format).date()
    except ValueError:
        return False

    minsk_now = datetime.datetime.now(ZoneInfo("Europe/Minsk"))
    current_date = minsk_now.date()
    current_time = minsk_now.time()
    if input_date < current_date or (
        input_date == current_date and input_time < current_time
    ):
        return False

    logger.bind(
        checked_date=input_date, checked_time=input_time, chat_id=chat_id
    ).debug(f"Valid time params: {date_str}, {time_str}")
    return True

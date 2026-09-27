import asyncio
import logging
from typing import override

import aiohttp
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.http_session import HttpSession
from app.interfaces import IRWApiClient
from app.schemas import ScheduleRequest
from app.settings import ProxySettings, RWApiSettings


class AsyncRWApiClient(IRWApiClient):
    BASE_URL = "https://pass.rw.by/ru/route/"

    def __init__(
        self,
        http_session: HttpSession,
        rwapi_settings: RWApiSettings,
        proxy_settings: ProxySettings,
    ) -> None:
        self.http_session = http_session
        self.rwapi_settings = rwapi_settings
        self.proxy_settings = proxy_settings

        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing `%s`", self.__class__.__name__)

    def _get_proxy_url(self) -> str | None:
        if not self.proxy_settings.enabled:
            return None

        return (
            f"http://{self.proxy_settings.login}:"
            f"{self.proxy_settings.password}@"
            f"{self.proxy_settings.host}:"
            f"{self.proxy_settings.port}"
        )

    async def _fetch_schedule(self, request: ScheduleRequest) -> str:
        timeout = aiohttp.ClientTimeout(
            total=self.rwapi_settings.request_timeout,
        )

        self.logger.debug(
            "Fetching RW schedule: %s -> %s",
            request.departure_station,
            request.arrival_station,
        )

        async with self.http_session.session.get(
            self.BASE_URL,
            params={
                "from": request.departure_station,
                "to": request.arrival_station,
                "date": request.travel_date,
            },
            headers=self.rwapi_settings.headers,
            timeout=timeout,
            proxy=self._get_proxy_url(),
        ) as response:
            response.raise_for_status()
            return await response.text()

    @override
    async def fetch_schedule(self, request: ScheduleRequest) -> str:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self.rwapi_settings.retry_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=3),
            retry=retry_if_exception_type(
                (aiohttp.ClientError, asyncio.TimeoutError),
            ),
            reraise=True,
        )

        return await retrying(self._fetch_schedule, request)

import asyncio
import logging
from typing import override
from urllib.parse import urlencode

from playwright.async_api import (
    Browser,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.interfaces import IRWBrowserService
from app.schemas import TicketRequest
from app.settings import RWBrowserSettings


class PlaywrightRWBrowserService(IRWBrowserService):
    BASE_URL = "https://pass.rw.by/ru/route/"
    CASH_ONLY_TEXT = "Оставшиеся места можно приобрести только в билетной кассе"

    def __init__(self, settings: RWBrowserSettings) -> None:
        self.settings = settings

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing `%s`", self.__class__.__name__)

    @staticmethod
    def _build_url(ticket: TicketRequest) -> str:
        query = urlencode(
            {
                "from": ticket.departure_station,
                "to": ticket.arrival_station,
                "date": ticket.travel_date,
            }
        )
        return f"{PlaywrightRWBrowserService.BASE_URL}?{query}"

    @override
    async def start(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return

            self._playwright = await async_playwright().start()

            self._browser = await self._playwright.chromium.launch(
                headless=self.settings.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )

            self.logger.info("Playwright browser started")

    @override
    async def stop(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None

            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None

            self.logger.info("Playwright browser stopped")

    async def _get_browser(self) -> Browser:
        if self._browser is None:
            await self.start()

        if self._browser is None:
            raise RuntimeError("Browser failed to start")

        return self._browser

    @staticmethod
    async def _close_cookies(page: Page) -> None:
        popup = page.locator("#cookies-popup")

        if not await popup.is_visible():
            return

        accept_button = popup.locator("button")

        if await accept_button.count():
            await accept_button.first.click()
            return

        await page.evaluate(
            """
            const el = document.getElementById('cookies-popup');
            if (el) el.remove();
            """
        )

    @override
    async def has_only_disabled_places(self, ticket: TicketRequest) -> bool:
        browser = await self._get_browser()
        page = await browser.new_page()

        try:
            await page.goto(
                self._build_url(ticket),
                timeout=self.settings.navigation_timeout,
                wait_until="domcontentloaded",
            )

            await self._close_cookies(page)

            await page.wait_for_selector(
                ".sch-table__row-wrap",
                timeout=self.settings.selector_timeout,
                state="attached",
            )

            rows = page.locator(".sch-table__row-wrap")

            row = rows.filter(
                has=page.locator(
                    ".train-from-time",
                    has_text=ticket.travel_time,
                ),
            ).first

            if await row.count() == 0:
                return False

            button = row.locator("form.js-sch-item-form a.btn")

            if await button.count() == 0:
                return False

            await button.scroll_into_view_if_needed()

            await asyncio.gather(
                page.wait_for_load_state("domcontentloaded"),
                button.click(force=True),
            )

            try:
                await page.wait_for_selector(
                    f"text={self.CASH_ONLY_TEXT}",
                    timeout=self.settings.cash_only_timeout,
                    state="attached",
                )
            except PlaywrightTimeoutError:
                return False

            return True

        finally:
            await page.close()

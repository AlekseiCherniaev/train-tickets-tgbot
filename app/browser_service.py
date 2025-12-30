import asyncio

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, Browser


class BrowserService:
    CASH_ONLY_TEXT = "Оставшиеся места можно приобрести только в билетной кассе"

    _browser: Browser | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_browser(cls) -> Browser:
        async with cls._lock:
            if cls._browser is None:
                playwright = await async_playwright().start()
                cls._browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                    ],
                )
            return cls._browser

    @classmethod
    async def close(cls) -> None:
        if cls._browser:
            await cls._browser.close()
            cls._browser = None

    @staticmethod
    async def close_cookies(page) -> None:
        popup = page.locator("#cookies-popup")
        if await popup.is_visible():
            accept_btn = popup.locator("button")
            if await accept_btn.count():
                await accept_btn.first.click()
            else:
                await page.evaluate(
                    """
                    const el = document.getElementById('cookies-popup');
                    if (el) el.remove();
                    """
                )

    @staticmethod
    async def has_only_disabled_places(
        from_station: str,
        to_station: str,
        date: str,
        train_time: str,
    ) -> bool:
        browser = await BrowserService.get_browser()
        page = await browser.new_page()
        try:
            url = (
                "https://pass.rw.by/ru/route/"
                f"?from={from_station}&to={to_station}&date={date}"
            )

            await page.goto(url, timeout=20_000, wait_until="domcontentloaded")
            await BrowserService.close_cookies(page)

            await page.wait_for_selector(
                ".sch-table__row-wrap",
                timeout=10_000,
                state="attached",
            )

            rows = page.locator(".sch-table__row-wrap")
            if await rows.count() == 0:
                return False

            row = rows.filter(
                has=page.locator(".train-from-time", has_text=train_time),
            ).first

            if await row.count() == 0:
                return False

            button = row.locator("form.js-sch-item-form a.btn")
            await button.scroll_into_view_if_needed()

            await asyncio.gather(
                page.wait_for_load_state("domcontentloaded"),
                button.click(force=True),
            )

            try:
                await page.wait_for_selector(
                    f"text={BrowserService.CASH_ONLY_TEXT}",
                    timeout=5_000,
                    state="attached",
                )
                return True
            except PlaywrightTimeoutError:
                return False
        finally:
            await page.close()

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
    async def close(cls):
        if cls._browser:
            await cls._browser.close()
            cls._browser = None

    @staticmethod
    async def close_cookies(page):
        popup = page.locator("#cookies-popup")
        if await popup.is_visible():
            accept_btn = popup.locator("button")
            if await accept_btn.count():
                await accept_btn.first.click()
            else:
                await page.evaluate("""
                    const el = document.getElementById('cookies-popup');
                    if (el) el.remove();
                """)

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
            url = f"https://pass.rw.by/ru/route/?from={from_station}&to={to_station}&date={date}"
            await page.goto(url, timeout=20_000)
            await page.wait_for_selector(".sch-table__row-wrap", timeout=10_000)
            await BrowserService.close_cookies(page)

            row = page.locator(
                ".sch-table__row-wrap",
                has=page.locator(".train-from-time", has_text=train_time),
            ).first

            if not await row.count():
                return False

            button = row.locator("form.js-sch-item-form a.btn")
            await button.scroll_into_view_if_needed()

            await asyncio.gather(
                page.wait_for_load_state("networkidle"),
                button.click(force=True),
            )

            try:
                await page.wait_for_selector(
                    f"text={BrowserService.CASH_ONLY_TEXT}",
                    timeout=5_000,
                )
                return True
            except PlaywrightTimeoutError:
                return False
        finally:
            await page.close()

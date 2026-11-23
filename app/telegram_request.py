import asyncio
import logging

import httpx
from telegram.error import NetworkError, TimedOut
from telegram.request import HTTPXRequest

logger = logging.getLogger(__name__)


class RetryingHTTPXRequest(HTTPXRequest):
    """HTTPX request that retries connect failures.

    Telegram connections from some hosts are dropped intermittently at the TCP
    level. A connect error means the request never reached Telegram, so a retry
    is safe (unlike read timeouts, which are not retried to avoid duplicates).
    """

    def __init__(self, *args: object, retry_attempts: int = 4, retry_delay: float = 0.5, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay

    async def do_request(self, *args: object, **kwargs: object) -> tuple[int, bytes]:
        for attempt in range(1, self._retry_attempts + 1):
            try:
                return await super().do_request(*args, **kwargs)
            except (NetworkError, TimedOut) as error:
                cause = error.__cause__

                if not isinstance(cause, (httpx.ConnectError, httpx.ConnectTimeout)):
                    raise

                if attempt == self._retry_attempts:
                    raise

                logger.warning(
                    "Telegram connect failed (attempt %s/%s), retrying: %s",
                    attempt,
                    self._retry_attempts,
                    cause,
                )

                await asyncio.sleep(self._retry_delay * attempt)

        raise RuntimeError("unreachable")

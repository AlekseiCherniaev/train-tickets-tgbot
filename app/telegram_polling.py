import asyncio
import logging
from collections.abc import Sequence
from datetime import timedelta
from time import monotonic
from typing import Any, override

from telegram import Update
from telegram.ext import ExtBot

logger = logging.getLogger(__name__)


class PollingLoggingBot(ExtBot[None]):
    @override
    async def get_updates(
        self,
        offset: int | None = None,
        limit: int | None = None,
        timeout: int | timedelta | None = None,
        allowed_updates: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> tuple[Update, ...]:
        started_at = monotonic()
        logger.info("Telegram getUpdates started: offset=%s timeout=%s", offset, timeout)

        try:
            updates = await super().get_updates(
                offset=offset,
                limit=limit,
                timeout=timeout,
                allowed_updates=allowed_updates,
                **kwargs,
            )
        except asyncio.CancelledError:
            logger.info("Telegram getUpdates cancelled: offset=%s elapsed=%.2fs", offset, monotonic() - started_at)
            raise
        except Exception as error:
            # Exception messages can contain URLs with bot tokens or proxy credentials.
            logger.warning(
                "Telegram getUpdates failed: offset=%s elapsed=%.2fs type=%s cause=%s",
                offset,
                monotonic() - started_at,
                type(error).__name__,
                type(error.__cause__).__name__ if error.__cause__ is not None else None,
            )
            raise

        logger.info(
            "Telegram getUpdates succeeded: offset=%s elapsed=%.2fs updates=%s first_id=%s last_id=%s",
            offset,
            monotonic() - started_at,
            len(updates),
            updates[0].update_id if updates else None,
            updates[-1].update_id if updates else None,
        )
        return updates

import structlog

from app.bot import TicketBot
from app.logger import prepare_logger
from app.settings import settings

logger = structlog.get_logger(__name__)


if __name__ == "__main__":
    prepare_logger(settings.log_level)
    ticket_bot = TicketBot(token=settings.bot_token)
    ticket_bot.start_bot()

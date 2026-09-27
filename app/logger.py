import logging


def prepare_logger(log_level: str) -> None:
    logging.basicConfig(
        level=log_level.upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    noisy_loggers = (
        "httpx",
        "httpcore",
        "telegram",
        "telegram.ext",
        "asyncio",
    )

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

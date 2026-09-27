from app.containers import Container
from app.logger import prepare_logger


def main() -> None:
    container = Container()

    settings = container.settings()
    prepare_logger(settings.log_level)

    bot = container.bot()
    bot.start()


if __name__ == "__main__":
    main()

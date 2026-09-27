from dependency_injector import containers, providers

from app.bot import TicketBot
from app.database.postgres_database import PostgresDatabase
from app.database.postgres_schema_initializer import PostgresSchemaInitializer
from app.handlers import TicketHandlers
from app.html_parser import BeautifulSoupHTMLParser
from app.http_session import HttpSession
from app.playwright_browser_service import PlaywrightRWBrowserService
from app.repositories.postgres_favorite_ticket import (
    PostgresFavoriteTicketRepository,
)
from app.repositories.postgres_ticket import PostgresTicketRepository
from app.rw_api_client import AsyncRWApiClient
from app.rw_client import RWClient
from app.settings import (
    PostgresSettings,
    ProxySettings,
    RWApiSettings,
    RWBrowserSettings,
    Settings,
)


class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings)
    postgres_settings = providers.Singleton(PostgresSettings)
    rw_api_settings = providers.Singleton(RWApiSettings)
    rw_browser_settings = providers.Singleton(RWBrowserSettings)
    proxy_settings = providers.Singleton(ProxySettings)

    http_session = providers.Singleton(HttpSession)

    database = providers.Singleton(
        PostgresDatabase,
        settings=postgres_settings,
    )

    schema_initializer = providers.Singleton(
        PostgresSchemaInitializer,
        database=database,
    )

    browser = providers.Singleton(
        PlaywrightRWBrowserService,
        settings=rw_browser_settings,
    )

    rw_api_client = providers.Singleton(
        AsyncRWApiClient,
        http_session=http_session,
        rwapi_settings=rw_api_settings,
        proxy_settings=proxy_settings,
    )

    html_parser = providers.Singleton(
        BeautifulSoupHTMLParser,
    )

    rw_client = providers.Singleton(
        RWClient,
        api=rw_api_client,
        browser=browser,
        parser=html_parser,
    )

    ticket_repository = providers.Singleton(
        PostgresTicketRepository,
        database=database,
    )

    favorite_repository = providers.Singleton(
        PostgresFavoriteTicketRepository,
        database=database,
        max_favorites=settings.provided.favorite_tickets_amount,
    )

    handlers = providers.Singleton(
        TicketHandlers,
        rw_client=rw_client,
        ticket_repository=ticket_repository,
        favorite_repository=favorite_repository,
    )

    bot = providers.Singleton(
        TicketBot,
        settings=settings,
        proxy_settings=proxy_settings,
        handlers=handlers,
        rw_client=rw_client,
        ticket_repository=ticket_repository,
        database=database,
        schema_initializer=schema_initializer,
        browser=browser,
        http_session=http_session,
    )

from app.interfaces import IRWBrowserService, IRWApiClient, IRWClient, IHTMLParser
from app.schemas import TicketRequest, TrainInfo


class RWClient(IRWClient):
    def __init__(
        self,
        api: IRWApiClient,
        browser: IRWBrowserService,
        parser: IHTMLParser,
    ):
        self._api = api
        self._browser = browser
        self._parser = parser

    async def validate(self, ticket: TicketRequest) -> bool:
        """Валидация билета перед добавлением в поиск"""
        page_html = await self._api.fetch_schedule(ticket)
        return self._parser.validate_response(ticket.travel_time, page_html)

    async def get_trains(self, ticket: TicketRequest) -> list[TrainInfo]:
        """Получение списка доступных поездов и мест"""
        page_html = await self._api.fetch_schedule(ticket)
        return self._parser.parse_trains_info(page_html)

    async def has_available_places(self, ticket: TicketRequest) -> bool:
        """Проверка, есть ли доступные места"""
        page_html = await self._api.fetch_schedule(ticket)

        if not self._parser.check_ticket_availability(ticket.travel_time, page_html):
            return False

        return not await self._browser.has_only_disabled_places(ticket)

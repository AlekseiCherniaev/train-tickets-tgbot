from typing import override

from app.exceptions import InvalidRouteError
from app.interfaces import IRWBrowserService, IRWApiClient, IRWClient, IHTMLParser
from app.schemas import TicketRequest, TrainInfo, ScheduleRequest, TicketAvailabilityStatus


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

    @override
    async def validate(self, request: TicketRequest) -> bool:
        page_html = await self._api.fetch_schedule(request)
        return self._parser.validate_response(request.travel_time, page_html)

    @override
    async def get_trains(
        self,
        request: ScheduleRequest,
    ) -> list[TrainInfo]:
        page_html = await self._api.fetch_schedule(request)

        if self._parser.has_errors(page_html):
            raise InvalidRouteError

        return self._parser.parse_trains_info(page_html)

    @override
    async def check_availability(
        self,
        request: TicketRequest,
    ) -> TicketAvailabilityStatus:
        page_html = await self._api.fetch_schedule(request)

        if not self._parser.validate_response(
            request.travel_time,
            page_html,
        ):
            return TicketAvailabilityStatus.INVALID

        if not self._parser.check_ticket_availability(
            request.travel_time,
            page_html,
        ):
            return TicketAvailabilityStatus.UNAVAILABLE

        if await self._browser.has_no_online_places(request):
            return TicketAvailabilityStatus.UNAVAILABLE

        return TicketAvailabilityStatus.AVAILABLE

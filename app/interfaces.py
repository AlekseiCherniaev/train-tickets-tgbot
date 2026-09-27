from abc import ABC, abstractmethod

from app.schemas import (
    TicketRequest,
    TicketRequestRecord,
    TrainInfo,
    NewTicketRequest,
    FavoriteTicket,
    ScheduleRequest,
    TicketAvailabilityStatus,
)


class IRWClient(ABC):
    @abstractmethod
    async def validate(self, request: TicketRequest) -> bool: ...

    @abstractmethod
    async def get_trains(self, request: ScheduleRequest) -> list[TrainInfo]: ...

    @abstractmethod
    async def check_availability(
        self,
        request: TicketRequest,
    ) -> TicketAvailabilityStatus: ...


class IRWApiClient(ABC):
    @abstractmethod
    async def fetch_schedule(self, request: ScheduleRequest) -> str: ...


class IRWBrowserService(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def has_no_online_places(self, ticket: TicketRequest) -> bool: ...


class IHTMLParser(ABC):
    @abstractmethod
    def validate_response(self, travel_time: str, page_html: str) -> bool: ...

    @abstractmethod
    def check_ticket_availability(self, travel_time: str, page_html: str) -> bool: ...

    @abstractmethod
    def parse_trains_info(self, page_html: str) -> list[TrainInfo]: ...

    @abstractmethod
    def has_errors(self, page_html: str) -> bool: ...


class ITicketRepository(ABC):
    @abstractmethod
    async def add_request(self, request: NewTicketRequest) -> int: ...

    @abstractmethod
    async def get_request_by_id(self, request_id: int) -> TicketRequestRecord | None: ...

    @abstractmethod
    async def get_active_requests(self) -> list[TicketRequestRecord]: ...

    @abstractmethod
    async def get_active_requests_by_chat(self, chat_id: int) -> list[TicketRequestRecord]: ...

    @abstractmethod
    async def get_chats_by_request(self, request: TicketRequest) -> list[int]: ...

    @abstractmethod
    async def deactivate_request(self, request: TicketRequest, chat_id: int) -> None: ...

    @abstractmethod
    async def deactivate_requests_by_chat(self, chat_id: int) -> int: ...


class IFavoriteTicketRepository(ABC):
    @abstractmethod
    async def add_favorite(self, ticket: FavoriteTicket, user_id: int) -> None: ...

    @abstractmethod
    async def get_favorites(self, user_id: int) -> list[FavoriteTicket]: ...

from abc import ABC, abstractmethod

from app.schemas import TicketRequest, TicketRequestRecord, TrainInfo


class IRWClient(ABC):
    @abstractmethod
    async def validate(self, ticket: TicketRequest) -> bool: ...

    @abstractmethod
    async def get_trains(self, ticket: TicketRequest) -> list[TrainInfo]: ...

    @abstractmethod
    async def has_available_places(self, ticket: TicketRequest) -> bool: ...


class IRWApiClient(ABC):
    @abstractmethod
    async def fetch_schedule(self, ticket: TicketRequest) -> str: ...


class IRWBrowserService(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def has_only_disabled_places(self, ticket: TicketRequest) -> bool: ...


class IHTMLParser(ABC):
    @abstractmethod
    def validate_response(self, travel_time: str, page_html: str) -> bool: ...

    @abstractmethod
    def check_ticket_availability(self, travel_time: str, page_html: str) -> bool: ...

    @abstractmethod
    def parse_trains_info(self, page_html: str) -> list[TrainInfo]: ...


class ITicketRepository(ABC):
    @abstractmethod
    async def add_request(self, request: TicketRequestRecord) -> int: ...

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
    async def deactivate_requests_by_chat(self, chat_id: int) -> None: ...


class IFavoriteTicketRepository(ABC):
    @abstractmethod
    async def add_favorite(self, ticket: TicketRequest, user_id: int) -> None: ...

    @abstractmethod
    async def get_favorite(self, user_id: int) -> list[TicketRequest]: ...

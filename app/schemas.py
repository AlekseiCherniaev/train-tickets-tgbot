from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(slots=True)
class FavoriteTicket:
    departure_station: str
    arrival_station: str
    travel_time: str


@dataclass(slots=True)
class ScheduleRequest:
    departure_station: str
    arrival_station: str
    travel_date: str


@dataclass(slots=True)
class TicketRequest(ScheduleRequest):
    travel_time: str


@dataclass(slots=True)
class NewTicketRequest(TicketRequest):
    chat_id: int
    user_id: int
    user_name: str | None


@dataclass(slots=True)
class TicketRequestRecord(NewTicketRequest):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class TrainPlace:
    name: str
    amount: int


@dataclass(slots=True)
class TrainInfo:
    departure_time: str
    arrival_time: str
    is_selling_allowed: bool
    places: list[TrainPlace]

    @property
    def total_places(self) -> int:
        return sum(p.amount for p in self.places)


class TicketAvailabilityStatus(StrEnum):
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"
    AVAILABLE = "available"

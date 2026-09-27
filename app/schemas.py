from dataclasses import dataclass


@dataclass(slots=True)
class TicketRequest:
    departure_station: str
    arrival_station: str
    travel_date: str
    travel_time: str


@dataclass(slots=True)
class TicketRequestRecord(TicketRequest):
    id: int
    chat_id: int
    user_id: int
    user_name: str | None
    is_active: bool


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
    def total_places(self):
        return sum(p.amount for p in self.places)

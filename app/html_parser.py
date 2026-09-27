import logging
from typing import override

from bs4 import BeautifulSoup, Tag

from app.interfaces import IHTMLParser
from app.schemas import TrainInfo, TrainPlace


class BeautifulSoupHTMLParser(IHTMLParser):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing `%s`", self.__class__.__name__)

    @staticmethod
    def _parse_html(page_html: str) -> BeautifulSoup:
        return BeautifulSoup(page_html, "html.parser")

    @override
    def validate_response(self, travel_time: str, page_html: str) -> bool:
        soup = self._parse_html(page_html)

        if self._has_error_elements(soup):
            self.logger.debug("HTML has error elements")
            return False

        if not self._contains_train_time(soup, travel_time):
            self.logger.debug("Travel time %s not found", travel_time)
            return False

        self.logger.debug("Valid train time %s", travel_time)
        return True

    @staticmethod
    def _has_error_elements(soup: BeautifulSoup) -> bool:
        return any(
            (
                soup.find("div", class_="error_content"),
                soup.find("div", class_="error_title"),
            )
        )

    @staticmethod
    def _contains_train_time(soup: BeautifulSoup, travel_time: str) -> bool:
        return soup.find("div", class_="sch-table__time train-from-time", string=travel_time) is not None

    @override
    def check_ticket_availability(self, travel_time: str, page_html: str) -> bool:
        soup = self._parse_html(page_html)
        target_block = soup.find(
            "div",
            class_="sch-table__time train-from-time",
            string=travel_time,
        )
        if not target_block:
            self.logger.debug("Target block with time %s not found", travel_time)
            return False

        parent_block = target_block.find_parent("div", class_="sch-table__row")
        if not parent_block:
            self.logger.debug("No parent block with time %s", travel_time)
            return False

        return parent_block.get("data-ticket_selling_allowed", "").lower() == "true"  # noqa

    @override
    def parse_trains_info(self, page_html: str) -> list[TrainInfo]:
        soup = self._parse_html(page_html)

        trains: list[TrainInfo] = []
        for row in soup.select("div.sch-table__row"):
            train = self._parse_train(row)
            if train is not None:
                trains.append(train)

        return sorted(trains, key=lambda t: t.departure_time)

    def _parse_train(self, row: Tag) -> TrainInfo | None:
        departure_time_element = row.select_one("div.sch-table__time.train-from-time")
        if not departure_time_element:
            self.logger.debug("No departure time element found")
            return None

        departure_time = departure_time_element.get_text(strip=True)

        arrival_time_element = row.select_one("div.sch-table__time.train-to-time")
        if not arrival_time_element:
            self.logger.debug("No arrival time element found")
            return None

        arrival_time = arrival_time_element.get_text(strip=True)

        is_selling_allowed = row.get("data-ticket_selling_allowed", "").lower() == "true"  # noqa

        places: list[TrainPlace] = []
        for ticket_item in row.select("div.sch-table__t-item"):
            place = self._parse_place(ticket_item)
            if place is not None:
                places.append(place)

        return TrainInfo(
            departure_time=departure_time,
            arrival_time=arrival_time,
            is_selling_allowed=is_selling_allowed,
            places=places,
        )

    def _parse_place(self, ticket_item: Tag) -> TrainPlace | None:
        amount_anchor = ticket_item.select_one("a.sch-table__t-quant")
        if amount_anchor is None:
            self.logger.debug("No amount anchor found")
            return None

        amount_element = amount_anchor.select_one("span")
        if amount_element is None:
            self.logger.debug("No amount element found")
            return None

        amount_text = amount_element.get_text(strip=True)
        if not amount_text.isdigit() or int(amount_text) <= 0:
            self.logger.debug("Amount text is not valid")
            return None

        name_element = ticket_item.select_one("div.sch-table__t-name")
        name = name_element.get_text(strip=True) if name_element is not None else "Места"

        return TrainPlace(
            name=name,
            amount=int(amount_text),
        )

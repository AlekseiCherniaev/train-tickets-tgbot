import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


class TicketParser:
    def __init__(self, response: str):
        self.soup = BeautifulSoup(response, "html.parser")

    def get_train_block(self, train_time: str):
        target_block = self.soup.find(
            "div",
            class_="sch-table__time train-from-time",
            string=train_time,
        )
        if not target_block:
            return None

        return target_block.find_parent("div", class_="sch-table__row")

    @staticmethod
    def check_ticket_availability(train_block: dict):
        return train_block.get("data-ticket_selling_allowed", "").lower() == "true"

    def validate_rzd_response(self, chat_id: int) -> bool:
        logger.bind(chat_id=chat_id).debug("Validating train params...")
        error_elements = {
            "error_content": self.soup.find("div", class_="error_content"),
            "error_title": self.soup.find("div", class_="error_title"),
        }
        if any(error_elements.values()):
            logger.bind(chat_id=chat_id).debug("RZD request error")
            return False
        return True

    def validate_train_time(self, train_time: str, chat_id: int) -> bool:
        if not self.soup.find("div", class_="sch-table__time train-from-time", string=train_time):
            logger.bind(train_time=train_time, chat_id=chat_id).debug("Departure time not found")
            return False

        logger.bind(params=train_time, chat_id=chat_id).debug(f"Valid train time: {train_time}")
        return True

    def parse_response(self) -> dict:
        trains: list[dict] = []

        for row in self.soup.select("div.sch-table__row"):
            dep_time_el = row.select_one("div.sch-table__time.train-from-time")
            departure_time = dep_time_el.get_text(strip=True) if dep_time_el is not None else ""
            if not departure_time:
                continue

            arr_time_el = row.select_one("div.sch-table__time.train-to-time")
            arrival_time = arr_time_el.get_text(strip=True) if arr_time_el is not None else ""

            is_selling_allowed = row.get("data-ticket_selling_allowed", "").lower() == "true"

            places: list[dict] = []
            for ticket_item in row.select("div.sch-table__t-item"):
                quant_anchor = ticket_item.select_one("a.sch-table__t-quant")
                if quant_anchor is None:
                    continue

                quant_el = quant_anchor.select_one("span")
                if quant_el is None:
                    continue

                quant_text = quant_el.get_text(strip=True)
                if not quant_text.isdigit() or int(quant_text) <= 0:
                    continue

                name_el = ticket_item.select_one("div.sch-table__t-name")
                name = name_el.get_text(strip=True) if name_el is not None else ""
                name = name.strip() or "Места"

                places.append({"name": name, "quantity": int(quant_text)})

            trains.append(
                {
                    "departure_time": departure_time,
                    "arrival_time": arrival_time,
                    "is_ticket_selling_allowed": is_selling_allowed,
                    "places": places,
                    "total_places": sum(p["quantity"] for p in places),
                }
            )

        trains.sort(key=lambda t: t["departure_time"])
        return {"trains": trains, "count": len(trains)}

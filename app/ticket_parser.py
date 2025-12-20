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
        # TODO check invalid and velo
        return train_block.get("data-ticket_selling_allowed", "").lower() == "true"

    def validate_rzd_response(self, params: list | tuple, chat_id: int):
        logger.bind(params=params, chat_id=chat_id).debug("Validating train params...")
        error_elements = {
            "error_content": self.soup.find("div", class_="error_content"),
            "error_title": self.soup.find("div", class_="error_title"),
        }
        if any(error_elements.values()):
            logger.bind(params=params, chat_id=chat_id).debug("RZD request error")
            return False

        # Check if train time exists
        if not self.soup.find(
            "div", class_="sch-table__time train-from-time", string=params[3]
        ):
            logger.bind(params=params, chat_id=chat_id).debug(
                "Departure time not found"
            )
            return False

        logger.bind(params=params, chat_id=chat_id).debug(
            f"Valid train params: {params}"
        )
        return True

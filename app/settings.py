from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    log_level: str = "INFO"
    favorite_tickets_amount: int = 7
    retry_time: float = 7.0
    request_delay: float = 0.66
    check_concurrency: int = 3
    check_timeout: float = 45.0


class RWApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="RW_",
    )

    request_timeout: float = 7
    retry_attempts: int = 8
    headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }


class RWBackgroundApiSettings(RWApiSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="RW_BACKGROUND_",
    )

    request_timeout: float = 1.3
    retry_attempts: int = 1


class RWBrowserSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="RW_BROWSER_",
    )

    headless: bool = True
    navigation_timeout: int = 10_000
    selector_timeout: int = 10_000
    cash_only_timeout: int = 5_000


class ProxySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="PROXY_",
    )

    login: str = ""
    password: str = ""
    host: str = ""
    port: int = 10500

    @field_validator("port", mode="before")
    @classmethod
    def _empty_port_as_default(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return 10500

        return value

    @property
    def is_configured(self) -> bool:
        return bool(self.host)

    def build_url(self) -> str | None:
        if not self.is_configured:
            return None

        credentials = f"{self.login}:{self.password}@" if self.login else ""

        return f"http://{credentials}{self.host}:{self.port}"


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="POSTGRES_",
    )

    user: str = "postgres"
    password: str = "postgres"
    db: str = "postgres"
    host: str = "localhost"
    port: int = 5432

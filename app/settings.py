from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    log_level: str = "INFO"
    favorite_tickets_amount: int = 7
    retry_time: float = 7.0  # seconds for another ticket finding retry
    request_delay: float = 0.66


class RWApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_prefix="RW_")

    request_timeout: float = 7
    retry_attempts: int = 8
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }


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
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_prefix="PROXY_")

    enabled: bool = False
    login: str = ""
    password: str = ""
    host: str = ""
    port: int = 10500


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_prefix="POSTGRES_"
    )

    user: str = "postgres"
    password: str = "postgres"
    db: str = "postgres"
    host: str = "localhost"
    port: int = 5432

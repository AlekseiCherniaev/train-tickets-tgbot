from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, frozen=True, env_file=".env", env_ignore_empty=True
    )

    bot_token: str = "BOT_TOKEN"
    log_level: str = "INFO"
    date_format: str = "%Y-%m-%d"

    retry_time: float = 7.0  # seconds for another ticket finding retry
    request_timeout: float = 7
    retry_attempts: int = 8
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    # proxy settings
    use_proxy: bool = False
    proxy_login: str = ""
    proxy_password: str = ""
    proxy_host: str = ""
    proxy_port: int = 10500
    # db settings
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432


settings = Settings()

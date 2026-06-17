from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/glamira"

    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    reset_link_base_url: str = "https://glamira.app/reset-password"
    reset_token_expire_minutes: int = 15

    # Google OAuth Web client id — the audience the mobile app's ID token is
    # issued for (passed as serverClientId in the app). Required for /auth/google.
    google_client_id: str | None = None

    cors_origins: str = "*"

    # Optional SMTP. When unset, reset links are logged to the console.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@glamira.app"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

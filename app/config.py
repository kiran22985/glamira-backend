from functools import lru_cache

from pydantic import field_validator
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
    smtp_from_name: str = "Glamira"

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """Normalize the DB URL to the async driver.

        Hosts like Render provide a psycopg-style URL (``postgres://`` or
        ``postgresql://``), but our engine uses asyncpg and needs its own
        ``+asyncpg`` prefix. Rewrite it so the same code runs locally and in prod.
        """
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

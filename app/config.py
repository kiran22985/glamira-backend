from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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

    # Cloudinary, as a single credential URL: cloudinary://<key>:<secret>@<cloud>
    # Copy it from the Cloudinary console (Settings -> API Keys). When unset,
    # the image upload endpoints return 503 rather than failing obscurely.
    cloudinary_url: str | None = None

    # Optional SMTP. When unset, reset links are logged to the console.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@glamira.app"
    smtp_from_name: str = "Glamira"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Normalize the DB URL for the asyncpg driver.

        Hosts hand out a psycopg-style URL (``postgres://`` / ``postgresql://``)
        often with libpq-only query params (``sslmode``, ``channel_binding``).
        Our engine uses asyncpg, which needs the ``+asyncpg`` scheme and rejects
        those params. Rewrite the scheme and drop the params — asyncpg still
        negotiates SSL by default, so external DBs (e.g. Neon) connect fine.
        """
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                v = "postgresql+asyncpg://" + v[len(prefix):]
                break

        parts = urlsplit(v)
        if parts.query:
            kept = [
                (k, val)
                for k, val in parse_qsl(parts.query)
                if k not in ("sslmode", "channel_binding")
            ]
            v = urlunsplit(parts._replace(query=urlencode(kept)))
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

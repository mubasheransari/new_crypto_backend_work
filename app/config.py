import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Vercel's serverless filesystem is read-only except /tmp. If DATABASE_URL
# isn't explicitly set via env vars, fall back to a path SQLite can actually
# write to when running there. Note: /tmp is wiped on every cold start and
# isn't shared across instances, so this is fine for testing but not for
# real persistence - use a hosted Postgres (Neon, Supabase, Vercel Postgres)
# and set DATABASE_URL in the Vercel project settings for production use.
_default_db_url = (
    "sqlite:////tmp/crypto_app.db" if os.environ.get("VERCEL") else "sqlite:///./crypto_app.db"
)


class Settings(BaseSettings):
    secret_key: str = "dev-secret-change-me"
    gemini_api_key: str = ""
    cryptocompare_api_key: str = ""
    admin_api_key: str = "change-this-admin-key"
    database_url: str = _default_db_url
    allowed_origins: str = "*"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

from datetime import tzinfo
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    App config loaded from environment / .env.
    pydantic-settings reads .env automatically when model_config points at it.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    app_timezone: str = "America/New_York"

    # Google Calendar (optional)
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_refresh_token: str | None = None

    # Claude & ElevenLabs (optional, for debrief)
    claude_api_key: str | None = None
    elevenlabs_api_key: str | None = None

    # Gmail SMTP (optional, for weekly debrief email)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None

    @property
    def tz(self) -> tzinfo:
        return ZoneInfo(self.app_timezone)

    @property
    def google_calendar_enabled(self) -> bool:
        return all([self.google_client_id, self.google_client_secret, self.google_refresh_token])

    @property
    def debrief_enabled(self) -> bool:
        return bool(self.claude_api_key and self.elevenlabs_api_key)

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)


# Module-level singleton: env vars do not change between requests, and pydantic
# validation is not free, so parsing once at import beats parsing per call.
settings = Settings()

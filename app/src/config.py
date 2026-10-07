from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- База данных ---
    DATABASE_URL: str
    DB_SCHEMA: str = "public"

    # --- Безопасность ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Приложение ---
    APP_PREFIX: str = ""
    APP_BASE_URL: str = "http://127.0.0.1:8000"     # ← НОВОЕ

    # --- Email / SMTP ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_SSL: bool = True

    # --- OAuth (Google) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # --- OAuth (GitHub) — опционально ---
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


# from pathlib import Path
# BASE_DIR = Path(__file__).resolve().parents[2]
        # env_file=BASE_DIR / ".env",

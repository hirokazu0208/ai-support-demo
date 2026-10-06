from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ ディレクトリ。起動したディレクトリに依存せずパスを解決するための基準
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = BACKEND_DIR / "data" / "app.db"


class Settings(BaseSettings):
    """アプリケーション設定。環境変数 → backend/.env → 既定値の順で解決する。"""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8"
    )

    database_url: str = f"sqlite:///{DEFAULT_SQLITE_PATH}"


settings = Settings()

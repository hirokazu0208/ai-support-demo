from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ ディレクトリ。起動したディレクトリに依存せずパスを解決するための基準
BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = BACKEND_DIR / "data" / "app.db"


class Settings(BaseSettings):
    """アプリケーション設定。環境変数 → backend/.env → 既定値の順で解決する。

    設定が不正な場合は Settings() の生成時（アプリ起動時）に ValidationError になる。
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        # 設定エラーのメッセージ（str / repr）に入力値を含めない。
        # 不正な項目名と理由は表示し、API キー・DB のパスワードなどの値そのものは表示しない
        hide_input_in_errors=True,
    )

    database_url: str = f"sqlite:///{DEFAULT_SQLITE_PATH}"

    # --- AI Agent（Demo 3 Step 5）-------------------------------------------------
    # rule: RuleBasedAgent（外部 LLM なし。既定）/ openai: LLM Agent（OpenAI Responses API）
    agent_provider: Literal["rule", "openai"] = "rule"
    # LLM / API 側の障害時に RuleBasedAgent で応答する（DB 障害ではフォールバックしない）
    agent_fallback_to_rule: bool = True
    # LLM Agent 1 回の応答で LLM を呼ぶ最大回数（Tool 呼び出しの往復。最後の締めの呼び出しは別）
    agent_max_llm_rounds: int = Field(default=3, ge=1, le=10)
    # LLM Agent 1 回の応答で実行する Tool の最大回数（全 Tool 合計）
    agent_max_tool_calls: int = Field(default=4, ge=1, le=10)
    # LLM Agent 1 回の応答にかける最大時間（秒）
    agent_timeout_seconds: float = Field(default=20.0, gt=0, le=120)

    # --- OpenAI（agent_provider=openai の場合のみ使用）------------------------------
    # API キーは SecretStr で保持し、repr / ログに値を出さない。コードに既定値は持たない
    openai_api_key: SecretStr | None = None
    # モデル名もコードに固定しない（openai の場合は必須）
    openai_model: str | None = None
    # OpenAI 互換エンドポイント（未指定なら SDK の既定）。将来の Azure 等への差し替え用
    openai_base_url: str | None = None
    # OpenAI API 1 回の呼び出しのタイムアウト（秒）と、SDK の再試行回数
    openai_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    openai_max_retries: int = Field(default=1, ge=0, le=5)
    # 1 回の LLM 応答の最大出力トークン数
    openai_max_output_tokens: int = Field(default=800, ge=1, le=4000)

    @field_validator("openai_model", "openai_base_url", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        """.env の「OPENAI_MODEL=」のような空の値は未設定として扱う。"""
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _require_openai_settings(self) -> Self:
        """agent_provider=openai の場合のみ、API キーとモデル名を必須にする。"""
        if self.agent_provider != "openai":
            return self
        missing = []
        if self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip():
            missing.append("OPENAI_API_KEY")
        if self.openai_model is None:
            missing.append("OPENAI_MODEL")
        if missing:
            # 値そのもの（API キー）はメッセージに含めない
            raise ValueError(
                f"AGENT_PROVIDER=openai の場合は {' と '.join(missing)} を設定してください"
            )
        return self


settings = Settings()

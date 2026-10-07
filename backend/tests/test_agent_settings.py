"""Agent Provider 設定（Demo 3 Step 5）のテスト。backend/.env は読まない（_env_file=None）。"""

import pytest
from pydantic import ValidationError

from app.config import Settings

AGENT_ENV_NAMES = [
    "AGENT_PROVIDER",
    "AGENT_FALLBACK_TO_RULE",
    "AGENT_MAX_LLM_ROUNDS",
    "AGENT_MAX_TOOL_CALLS",
    "AGENT_TIMEOUT_SECONDS",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "OPENAI_TIMEOUT_SECONDS",
    "OPENAI_MAX_RETRIES",
    "OPENAI_MAX_OUTPUT_TOKENS",
]
FAKE_KEY = "sk-test-do-not-leak-0123456789"


@pytest.fixture(autouse=True)
def clean_agent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """実行環境の環境変数に影響されないようにする。"""
    for name in AGENT_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def make_settings(**env: str) -> Settings:
    return Settings(_env_file=None, **env)  # type: ignore[arg-type]


def test_defaults() -> None:
    settings = make_settings()

    assert settings.agent_provider == "rule"
    assert settings.agent_fallback_to_rule is True
    assert settings.openai_api_key is None
    assert settings.openai_model is None
    assert settings.openai_base_url is None
    assert settings.openai_timeout_seconds == 10.0
    assert settings.openai_max_retries == 1
    assert settings.openai_max_output_tokens == 800
    assert settings.agent_max_llm_rounds == 3
    assert settings.agent_max_tool_calls == 4
    assert settings.agent_timeout_seconds == 20.0


def test_rule_provider_does_not_require_openai_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "rule")

    assert Settings(_env_file=None).agent_provider == "rule"


def test_openai_provider_with_key_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")

    settings = Settings(_env_file=None)

    assert settings.agent_provider == "openai"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == FAKE_KEY
    assert settings.openai_model == "test-model"


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({"OPENAI_MODEL": "test-model"}, "OPENAI_API_KEY"),
        ({"OPENAI_API_KEY": FAKE_KEY}, "OPENAI_MODEL"),
        ({}, "OPENAI_API_KEY と OPENAI_MODEL"),
        ({"OPENAI_API_KEY": "  ", "OPENAI_MODEL": "test-model"}, "OPENAI_API_KEY"),
        ({"OPENAI_API_KEY": FAKE_KEY, "OPENAI_MODEL": " "}, "OPENAI_MODEL"),
    ],
)
def test_openai_provider_requires_key_and_model(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], missing: str
) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "openai")
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match=missing):
        Settings(_env_file=None)


@pytest.mark.parametrize("provider", ["azure", "OPENAI", "", "llm"])
def test_invalid_provider_is_rejected(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", provider)

    with pytest.raises(ValidationError, match="agent_provider"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AGENT_MAX_LLM_ROUNDS", "0"),
        ("AGENT_MAX_TOOL_CALLS", "11"),
        ("AGENT_TIMEOUT_SECONDS", "0"),
        ("OPENAI_TIMEOUT_SECONDS", "61"),
        ("OPENAI_MAX_RETRIES", "-1"),
        ("OPENAI_MAX_OUTPUT_TOKENS", "0"),
        ("AGENT_FALLBACK_TO_RULE", "maybe"),
    ],
)
def test_out_of_range_values_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_fallback_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_FALLBACK_TO_RULE", "false")

    assert Settings(_env_file=None).agent_fallback_to_rule is False


def test_blank_model_and_base_url_are_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "")
    monkeypatch.setenv("OPENAI_BASE_URL", "   ")

    settings = Settings(_env_file=None)

    assert settings.openai_model is None
    assert settings.openai_base_url is None


def test_api_key_is_not_exposed_in_repr_or_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    settings = Settings(_env_file=None)

    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings)
    assert FAKE_KEY not in repr(settings.openai_api_key)
    assert FAKE_KEY not in str(settings.model_dump())

    # 設定エラー時（モデル未設定）のメッセージにもキーを含めない
    monkeypatch.delenv("OPENAI_MODEL")
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert FAKE_KEY not in str(error.value)

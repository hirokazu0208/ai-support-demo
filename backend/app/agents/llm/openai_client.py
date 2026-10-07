"""OpenAI Responses API のアダプター（LLMClient Protocol の実装）。

LLMAgent はこのモジュールに依存しない（LLMClient Protocol だけを使う）。openai SDK を import するのは
backend 全体でこのモジュールだけで、SDK 固有の型・例外はここで provider 中立の型（LLMTurn・LLMError）に変換する。

- 同期の OpenAI クライアントを使う（router・Agent・SQLAlchemy Session がすべて同期のため）
- store=False: 会話状態を OpenAI 側に保存しない。previous_response_id は使わず、
  前ターンの output items と function_call_output を毎回 input に積み上げて送る
- モデル名・API キーはコードに持たず Settings（OPENAI_MODEL / OPENAI_API_KEY）から受け取る
"""

import copy
from typing import Any

import httpx2
import openai
from openai import OpenAI

from app.agents.llm.client import (
    LLMFunctionCall,
    LLMProviderError,
    LLMRequest,
    LLMResponseError,
    LLMTurn,
)
from app.config import Settings

# store=False でも推論モデルの reasoning item を次ターンへ引き継げるよう、暗号化された推論内容を受け取る
_INCLUDE = ["reasoning.encrypted_content"]


class OpenAIResponsesClient:
    """LLMRequest を responses.create() に変換し、応答を LLMTurn に変換する。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 1,
        http_client: httpx2.Client | None = None,
    ) -> None:
        if not api_key.strip() or not model.strip():
            raise ValueError("OpenAI の API キーとモデル名が必要です")
        self._model = model
        # API キーは SDK クライアントの内部にのみ保持する（このクラスの属性・repr には持たない）
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=http_client,
        )

    @classmethod
    def from_settings(
        cls, settings: Settings, *, http_client: httpx2.Client | None = None
    ) -> "OpenAIResponsesClient":
        if settings.openai_api_key is None or settings.openai_model is None:
            raise ValueError("OPENAI_API_KEY と OPENAI_MODEL を設定してください")
        return cls(
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
            http_client=http_client,
        )

    @property
    def model(self) -> str:
        return self._model

    def create_turn(self, request: LLMRequest) -> LLMTurn:
        params = build_request_params(self._model, request)
        try:
            response = self._client.responses.create(**params)
        except openai.APIError as error:
            # SDK 固有の例外を provider 中立の例外に変換する（元の例外の連鎖は切り、内容を漏らさない）
            raise to_provider_error(error) from None
        return parse_response(response)


def build_request_params(model: str, request: LLMRequest) -> dict[str, Any]:
    """LLMRequest から responses.create() の引数を作る。"""
    params: dict[str, Any] = {
        "model": model,
        "instructions": request.instructions,
        "input": copy.deepcopy(request.input_items),
        "tools": copy.deepcopy(request.tools),
        "tool_choice": request.tool_choice,
        "parallel_tool_calls": request.parallel_tool_calls,
        "max_output_tokens": request.max_output_tokens,
        "store": False,
        "include": list(_INCLUDE),
    }
    if request.max_tool_calls is not None:
        params["max_tool_calls"] = request.max_tool_calls
    return params


def parse_response(response: Any) -> LLMTurn:
    """Responses API の応答を LLMTurn に変換する（output items は素の dict にする）。"""
    if response.status in ("failed", "cancelled"):
        raise LLMResponseError(f"LLM response status: {response.status}")

    function_calls: list[LLMFunctionCall] = []
    output_items: list[dict[str, Any]] = []
    for item in response.output or []:
        output_items.append(item.to_dict(mode="json"))
        if item.type != "function_call":
            continue
        call_id, name, arguments = item.call_id, item.name, item.arguments
        if not (isinstance(call_id, str) and call_id and isinstance(name, str) and name):
            raise LLMResponseError("LLM returned a malformed function call")
        if not isinstance(arguments, str):
            raise LLMResponseError("LLM returned malformed function call arguments")
        function_calls.append(LLMFunctionCall(call_id=call_id, name=name, arguments=arguments))

    return LLMTurn(
        function_calls=function_calls,
        output_text=response.output_text or "",
        output_items=output_items,
    )


def to_provider_error(error: openai.APIError) -> LLMProviderError:
    """openai SDK の例外を LLMProviderError に変換する（キー・プロンプトは含めない）。"""
    status_code: int | None = None
    request_id: str | None = None
    if isinstance(error, openai.APIStatusError):
        status_code, request_id = error.status_code, error.request_id
    if isinstance(error, openai.APITimeoutError):  # APIConnectionError のサブクラスなので先に判定する
        kind = "timeout"
    elif isinstance(error, openai.APIConnectionError):
        kind = "connection"
    elif isinstance(error, openai.RateLimitError):
        kind = "rate_limit"
    elif isinstance(error, openai.AuthenticationError):
        kind = "authentication"
    elif isinstance(error, openai.PermissionDeniedError):
        kind = "permission"
    elif isinstance(error, openai.InternalServerError):
        kind = "server"
    elif isinstance(error, openai.APIStatusError) and 400 <= error.status_code < 500:
        kind = "bad_request"
    else:
        kind = "api"
    return LLMProviderError(kind, status_code=status_code, request_id=request_id)

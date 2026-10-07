"""LLM プロバイダに依存しない Protocol と型。

LLMAgent はこの Protocol にだけ依存する。OpenAI などの SDK 固有の型はここに出さず、
SDK との変換は各プロバイダのアダプター（Demo 3 Step 5-C 以降）が担当する。
入出力の items は Responses API の形にならった素の dict で表す。
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

# required: いずれかの Tool を必ず呼ぶ / auto: LLM が判断する / none: Tool を呼ばずテキストで答える
ToolChoice = Literal["required", "auto", "none"]


@dataclass(frozen=True)
class LLMFunctionCall:
    """LLM が要求した Tool の呼び出し。arguments は未検証の JSON 文字列。"""

    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class LLMTurn:
    """LLM 1 回分の応答。

    function_calls: LLM が要求した Tool 呼び出し（なければ最終回答）
    output_text: LLM のテキスト出力
    output_items: 次のターンの input にそのまま積む出力 items（会話の継続に必要な情報）
    """

    function_calls: list[LLMFunctionCall] = field(default_factory=list)
    output_text: str = ""
    output_items: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LLMRequest:
    """LLMAgent が LLM に 1 ターン分の処理を要求するときの内容。"""

    instructions: str
    input_items: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    tool_choice: ToolChoice
    max_output_tokens: int
    # 1 ターンで LLM が要求できる Tool 呼び出しの数（プロバイダ側の制限。None は指定なし）
    max_tool_calls: int | None = 1
    parallel_tool_calls: bool = False


class LLMClient(Protocol):
    """1 ターン分の LLM 処理を行うクライアント。プロバイダごとのアダプターが実装する。

    失敗時は LLMError（またはそのサブクラス）を送出する。
    """

    def create_turn(self, request: LLMRequest) -> LLMTurn: ...


class LLMError(Exception):
    """LLM 層の失敗（プロバイダ呼び出しの失敗・応答の不正・上限超過・時間切れ）。"""


class LLMResponseError(LLMError):
    """LLM の応答が不正、または上限内で最終回答に到達しなかった。"""


class LLMTimeoutError(LLMError):
    """LLM Agent 全体の時間上限を超えた。"""

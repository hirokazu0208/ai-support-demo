"""LLM Agent のテスト用の Fake（OpenAI API を呼ばない）。"""

import copy
import json
from collections.abc import Callable, Iterable
from typing import Any

from app.agents.llm.client import LLMFunctionCall, LLMRequest, LLMTurn


def function_call(name: str, arguments: dict[str, Any] | str, call_id: str) -> LLMFunctionCall:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False)
    return LLMFunctionCall(call_id=call_id, name=name, arguments=raw)


def tool_turn(*calls: LLMFunctionCall) -> LLMTurn:
    """Tool を要求する LLM のターン（Responses API の function_call items 相当）。"""
    return LLMTurn(
        function_calls=list(calls),
        output_items=[
            {"type": "function_call", "call_id": c.call_id, "name": c.name, "arguments": c.arguments}
            for c in calls
        ],
    )


def text_turn(text: str) -> LLMTurn:
    """最終テキストを返す LLM のターン。"""
    return LLMTurn(
        output_text=text,
        output_items=[
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    )


class FakeLLMClient:
    """事前に設定した LLMTurn（または例外）を順番に返し、受け取った要求を記録する。"""

    def __init__(
        self,
        turns: Iterable[LLMTurn | Exception],
        on_call: Callable[[int], None] | None = None,
    ) -> None:
        self._turns = list(turns)
        self._on_call = on_call
        self.requests: list[LLMRequest] = []

    def create_turn(self, request: LLMRequest) -> LLMTurn:
        # Agent が後で items を変更しても記録が変わらないようコピーして保存する
        self.requests.append(copy.deepcopy(request))
        if self._on_call is not None:
            self._on_call(len(self.requests))
        if len(self.requests) > len(self._turns):
            raise AssertionError(f"unexpected LLM call #{len(self.requests)}")
        turn = self._turns[len(self.requests) - 1]
        if isinstance(turn, Exception):
            raise turn
        return turn

    @property
    def call_count(self) -> int:
        return len(self.requests)

    @property
    def tool_choices(self) -> list[str]:
        return [request.tool_choice for request in self.requests]

    @property
    def tools(self) -> list[list[dict[str, Any]]]:
        return [request.tools for request in self.requests]

    def function_outputs(self, request_index: int) -> dict[str, dict[str, Any]]:
        """指定した要求に含まれる function_call_output を call_id → output(dict) で返す。"""
        return {
            item["call_id"]: json.loads(item["output"])
            for item in self.requests[request_index].input_items
            if item.get("type") == "function_call_output"
        }


class FakeClock:
    """時刻を手動で進める時計（実際の sleep を使わずに時間上限をテストする）。"""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds

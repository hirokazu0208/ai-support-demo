"""LLM Agent。LLM が許可リストの Tool（search_faqs / draft_inquiry）を選んで呼び出す。

制御フロー:
  利用者のメッセージ → LLM（最初は tool_choice=required）→ function_call
  → Tool Registry で検証・実行 → function_call_output → LLM（tool_choice=auto）→ … → 最終テキスト
  → AgentReply（action・FAQ・起票案は Tool の実行結果から作る）

安全性はコード構造で保証する:
- LLM が呼べるのは app/tools/registry.py の許可リストの Tool だけ（登録・更新の Tool は存在しない）
- 未知の Tool・不正な引数・上限超過の呼び出しは実行せず、安全なエラー情報だけを LLM に返す
- LLM の文章に書かれた FAQ や起票案は AgentReply の構造化データに使わない
"""

import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentReply, ToolCall
from app.agents.llm.client import (
    LLMClient,
    LLMFunctionCall,
    LLMRequest,
    LLMResponseError,
    LLMTimeoutError,
    LLMTurn,
    ToolChoice,
)
from app.agents.llm.prompts import SYSTEM_INSTRUCTIONS
from app.agents.rule_based import DRAFT_GUIDE
from app.config import Settings
from app.repositories.faqs import FaqMatch
from app.schemas.inquiry import InquiryDraft
from app.tools.registry import (
    ToolArgumentsError,
    UnknownToolError,
    function_tool_definitions,
    get_function_tool,
)

# LLM に返す Tool のエラー（例外の内容やスタックトレースは含めない）
UNKNOWN_TOOL_ERROR = {
    "error": "unknown_tool",
    "message": "このツールは利用できません。利用できるツールは search_faqs と draft_inquiry だけです。",
}
INVALID_ARGUMENTS_ERROR = {
    "error": "invalid_arguments",
    "message": "ツールの引数が不正なため実行しませんでした。",
}
TOOL_LIMIT_ERROR = {
    "error": "tool_call_limit_reached",
    "message": "ツールの呼び出し上限に達したため実行しませんでした。これまでの結果をもとに回答してください。",
}


@dataclass(frozen=True)
class LLMAgentLimits:
    """LLM Agent の上限値（無限ループ・長時間化の防止）。"""

    max_llm_rounds: int = 3  # Tool 呼び出しの往復に使う LLM 呼び出し回数（最後の締めの 1 回は別）
    max_tool_calls: int = 4  # 1 回の応答で実行する Tool の合計回数
    timeout_seconds: float = 20.0  # 1 回の応答全体の時間
    max_output_tokens: int = 800  # LLM 1 回の最大出力トークン数
    max_message_length: int = 2000  # AgentReply.message の最大文字数（コードポイント）

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMAgentLimits":
        return cls(
            max_llm_rounds=settings.agent_max_llm_rounds,
            max_tool_calls=settings.agent_max_tool_calls,
            timeout_seconds=settings.agent_timeout_seconds,
            max_output_tokens=settings.openai_max_output_tokens,
        )


@dataclass
class _RunState:
    """1 回の応答の間の Tool 実行結果（AgentReply の構造化データはここからのみ作る）。"""

    tool_calls: list[ToolCall] = field(default_factory=list)
    calls_per_tool: Counter[str] = field(default_factory=Counter)
    matched_faqs: list[FaqMatch] = field(default_factory=list)
    inquiry_draft: InquiryDraft | None = None
    limit_reached: bool = False


class LLMAgent:
    """Agent プロトコル（respond(session, message) -> AgentReply）を実装する LLM Agent。"""

    def __init__(
        self,
        client: LLMClient,
        limits: LLMAgentLimits | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.limits = limits or LLMAgentLimits()
        self._clock = clock

    def respond(self, session: Session, message: str) -> AgentReply:
        deadline = self._clock() + self.limits.timeout_seconds
        state = _RunState()
        items: list[dict[str, Any]] = [{"role": "user", "content": message}]

        tool_choice: ToolChoice = "required"  # 最初は必ず Tool（FAQ 検索）を根拠にさせる
        for _ in range(self.limits.max_llm_rounds):
            turn = self._create_turn(items, tool_choice, deadline)
            if not turn.function_calls:
                return self._build_reply(turn.output_text, state)

            items.extend(turn.output_items)
            for call in turn.function_calls:
                output = self._run_tool(session, call, state)
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(output, ensure_ascii=False),
                    }
                )
            if state.limit_reached:
                break  # 上限に達したら、Tool なしで最終回答を求める
            tool_choice = "auto"

        # 往復の上限・Tool の上限に達した: Tool を使わせず最終テキストを要求する
        turn = self._create_turn(items, "none", deadline)
        if turn.function_calls:
            raise LLMResponseError("LLM requested tools after tool_choice=none")
        return self._build_reply(turn.output_text, state)

    # --- LLM 呼び出し -------------------------------------------------------------------

    def _create_turn(
        self, items: list[dict[str, Any]], tool_choice: ToolChoice, deadline: float
    ) -> LLMTurn:
        if self._clock() >= deadline:
            raise LLMTimeoutError("LLM agent timed out")
        turn = self.client.create_turn(
            LLMRequest(
                instructions=SYSTEM_INSTRUCTIONS,
                input_items=list(items),
                tools=function_tool_definitions(),
                tool_choice=tool_choice,
                max_output_tokens=self.limits.max_output_tokens,
                max_tool_calls=None if tool_choice == "none" else 1,
                parallel_tool_calls=False,
            )
        )
        if self._clock() >= deadline:
            raise LLMTimeoutError("LLM agent timed out")
        return turn

    # --- Tool 実行（許可リストの Tool だけを、検証済みの引数で実行する）----------------------

    def _run_tool(
        self, session: Session, call: LLMFunctionCall, state: _RunState
    ) -> dict[str, Any]:
        try:
            tool = get_function_tool(call.name)
        except UnknownToolError:
            return UNKNOWN_TOOL_ERROR

        executed_total = sum(state.calls_per_tool.values())
        if (
            executed_total >= self.limits.max_tool_calls
            or state.calls_per_tool[tool.name] >= tool.max_calls_per_reply
        ):
            state.limit_reached = True
            return TOOL_LIMIT_ERROR

        try:
            args = tool.parse_arguments(call.arguments)
        except ToolArgumentsError:
            return INVALID_ARGUMENTS_ERROR

        # DB の例外（SQLAlchemyError）はここで握りつぶさない（DB 障害は LLM の問題ではない）
        outcome = tool.execute(session, args)
        state.calls_per_tool[tool.name] += 1
        state.tool_calls.append(ToolCall(name=tool.name, arguments=outcome.arguments))
        known_ids = {match.faq.id for match in state.matched_faqs}
        state.matched_faqs.extend(m for m in outcome.matched_faqs if m.faq.id not in known_ids)
        if outcome.inquiry_draft is not None:
            state.inquiry_draft = outcome.inquiry_draft
        if sum(state.calls_per_tool.values()) >= self.limits.max_tool_calls:
            state.limit_reached = True
        return outcome.output

    # --- AgentReply の生成（構造化データは Tool の実行結果だけから作る）-----------------------

    def _build_reply(self, output_text: str, state: _RunState) -> AgentReply:
        text = output_text.strip()
        if not text:
            raise LLMResponseError("LLM returned an empty final response")
        text = "".join(list(text)[: self.limits.max_message_length]).rstrip()
        if state.inquiry_draft is not None:
            # 起票案があるときは「まだ登録されていない」ことを必ず明示する（LLM の文章に依存しない）
            text = f"{text}\n\n{DRAFT_GUIDE}"

        if state.inquiry_draft is not None:
            action = AgentAction.INQUIRY_DRAFTED
        elif state.matched_faqs:
            action = AgentAction.FAQ_ANSWER
        else:
            action = AgentAction.INQUIRY_SUGGESTED

        return AgentReply(
            message=text,
            action=action,
            matched_faqs=list(state.matched_faqs),
            tool_calls=list(state.tool_calls),
            inquiry_draft=state.inquiry_draft,
        )

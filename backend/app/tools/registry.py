"""LLM に公開する Function Tool の許可リスト（Demo 3 Step 5）。

LLM Agent が呼び出せる Tool は、ここに登録した 2 つ（search_faqs / draft_inquiry）だけ。
- 既存 Tool（faq_search / draft_inquiry）の NAME・DESCRIPTION・引数モデル・実行関数を再利用する
- Tool 名から任意の関数を動的に探して呼ぶことはしない（登録済みの実行関数だけを呼ぶ）
- 問い合わせの登録・更新を行う Tool は登録しない（登録は人が既存の登録画面から行う）
- repository や SQL は LLM に公開しない（LLM が渡せるのは JSON の引数だけ）
"""

import copy
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.repositories.faqs import FaqMatch
from app.schemas.inquiry import InquiryDraft
from app.tools import draft_inquiry, faq_search

# LLM Agent での FAQ 検索の件数（LLM には公開せずサーバー側で固定する）
LLM_FAQ_SEARCH_LIMIT = 3


class ToolExecutionError(Exception):
    """Tool を実行できない（LLM には内容を伏せたエラーとして返す）。"""


class UnknownToolError(ToolExecutionError):
    """許可リストにない Tool 名。"""


class ToolArgumentsError(ToolExecutionError):
    """Tool の引数が不正（JSON でない・公開していない項目・型や長さの違反）。"""


@dataclass(frozen=True)
class ToolOutcome:
    """Tool の実行結果。

    output: LLM へ返す JSON（function_call_output）
    arguments: 検証済みの引数（AgentReply.tool_calls の記録に使う）
    matched_faqs / inquiry_draft: AgentReply を組み立てるためのサーバー側の結果
    """

    output: dict[str, Any]
    arguments: dict[str, Any]
    matched_faqs: list[FaqMatch] = field(default_factory=list)
    inquiry_draft: InquiryDraft | None = None


@dataclass(frozen=True)
class FunctionTool:
    name: str
    description: str
    # LLM に見せる JSON Schema（型と説明のみ。長さ等の制約はサーバー側の args_model で検証する）
    parameters: Mapping[str, Any]
    # サーバー側で引数を検証する既存の Pydantic モデル
    args_model: type[BaseModel]
    # 1 回の応答で呼び出せる最大回数
    max_calls_per_reply: int
    _execute: Callable[[Session, Any], ToolOutcome]
    # LLM が指定できる項目（parameters の properties と同じ）。サーバー側で固定する値はここに含めない
    _fixed_arguments: Mapping[str, Any] = field(default_factory=dict)

    def definition(self) -> dict[str, Any]:
        """OpenAI Responses API の function tool 定義（strict モード）。"""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            # 呼び出し側が変更しても登録内容に影響しないよう、毎回コピーを返す
            "parameters": copy.deepcopy(dict(self.parameters)),
            "strict": True,
        }

    def parse_arguments(self, arguments_json: str) -> BaseModel:
        """LLM から受け取った引数（JSON 文字列）を検証する。公開していない項目は拒否する。"""
        try:
            data = json.loads(arguments_json)
        except (TypeError, ValueError) as error:
            raise ToolArgumentsError(f"{self.name}: arguments is not valid JSON") from error
        if not isinstance(data, dict):
            raise ToolArgumentsError(f"{self.name}: arguments must be a JSON object")
        allowed = set(self.parameters["properties"])
        unexpected = set(data) - allowed
        if unexpected:
            raise ToolArgumentsError(f"{self.name}: unexpected arguments {sorted(unexpected)}")
        try:
            return self.args_model.model_validate({**data, **self._fixed_arguments})
        except ValidationError as error:
            raise ToolArgumentsError(f"{self.name}: invalid arguments") from error

    def execute(self, session: Session, args: BaseModel) -> ToolOutcome:
        return self._execute(session, args)


def _string_property(model: type[BaseModel], name: str) -> dict[str, Any]:
    """既存の引数モデルの説明を再利用して、LLM 向けの文字列プロパティを作る。"""
    description = model.model_fields[name].description
    return {"type": "string", "description": description}


def _object_schema(properties: dict[str, Any]) -> dict[str, Any]:
    """strict モードで使える形（全項目 required・additionalProperties=false）。"""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _execute_search_faqs(session: Session, args: faq_search.FaqSearchArgs) -> ToolOutcome:
    matches = faq_search.search_faq_tool(session, args.query, limit=args.limit)
    return ToolOutcome(
        output={
            "faqs": [
                {
                    "id": match.faq.id,
                    "question": match.faq.question,
                    "answer": match.faq.answer,
                    "category": match.faq.category.value,
                    "score": match.score,
                }
                for match in matches
            ]
        },
        arguments={"query": args.query, "limit": args.limit},
        matched_faqs=matches,
    )


def _execute_draft_inquiry(
    _session: Session, args: draft_inquiry.DraftInquiryArgs
) -> ToolOutcome:
    # 起票案 Tool は DB を使わない（Session は渡さない）。登録はしない
    draft = draft_inquiry.draft_inquiry_tool(args.message)
    output: dict[str, Any] = (
        {"draft": draft.model_dump(mode="json")}
        if draft is not None
        else {"draft": None, "reason": "問い合わせの内容が不足しているため起票案を作成できませんでした"}
    )
    return ToolOutcome(output=output, arguments={"message": args.message}, inquiry_draft=draft)


_SEARCH_FAQS = FunctionTool(
    name=faq_search.NAME,
    description=faq_search.DESCRIPTION,
    parameters=_object_schema({"query": _string_property(faq_search.FaqSearchArgs, "query")}),
    args_model=faq_search.FaqSearchArgs,
    max_calls_per_reply=2,
    _execute=_execute_search_faqs,
    _fixed_arguments=MappingProxyType({"limit": LLM_FAQ_SEARCH_LIMIT}),
)

_DRAFT_INQUIRY = FunctionTool(
    name=draft_inquiry.NAME,
    description=draft_inquiry.DESCRIPTION,
    parameters=_object_schema(
        {"message": _string_property(draft_inquiry.DraftInquiryArgs, "message")}
    ),
    args_model=draft_inquiry.DraftInquiryArgs,
    max_calls_per_reply=1,
    _execute=_execute_draft_inquiry,
)

# 許可リスト（読み取り専用）。ここにない Tool は実行できない
FUNCTION_TOOLS: Mapping[str, FunctionTool] = MappingProxyType(
    {tool.name: tool for tool in (_SEARCH_FAQS, _DRAFT_INQUIRY)}
)


def function_tool_definitions() -> list[dict[str, Any]]:
    """LLM に渡す Tool 定義の一覧（呼び出しごとに新しいオブジェクトを返す）。"""
    return [tool.definition() for tool in FUNCTION_TOOLS.values()]


def get_function_tool(name: str) -> FunctionTool:
    """許可リストから Tool を取り出す。ない場合は UnknownToolError（動的な関数探索はしない）。"""
    tool = FUNCTION_TOOLS.get(name)
    if tool is None:
        raise UnknownToolError(f"unknown tool: {name!r}")
    return tool


def execute_function_tool(session: Session, name: str, arguments_json: str) -> ToolOutcome:
    """許可リストの Tool を、検証済みの引数で実行する。"""
    tool = get_function_tool(name)
    return tool.execute(session, tool.parse_arguments(arguments_json))

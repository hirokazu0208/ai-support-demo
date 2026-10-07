"""ルールベースの Agent。外部 LLM を使わず、決まった手順で Tool を選んで呼び出す。

判断ロジック（Demo 3 Step 4 時点）:
  1. 利用者が問い合わせの登録を明示的に依頼しているかを判定する（「問い合わせとして登録して」等）
  2. 依頼部分を除いた内容で FAQ 検索 Tool（search_faqs）を呼ぶ
  3. FAQ が見つかり、登録の依頼がなければ、FAQ をもとに回答する（FAQ_ANSWER）
  4. 登録の依頼がある、または FAQ が見つからなければ、起票案 Tool（draft_inquiry）を呼ぶ
     - 起票案を作れたら INQUIRY_DRAFTED（関連 FAQ があれば併せて返す）
     - 作れなければ（内容がない等）INQUIRY_SUGGESTED
Agent は問い合わせを DB に登録しない。登録は人が既存の登録画面で確認してから行う。
"""

from sqlalchemy.orm import Session

from app.agents.base import AgentAction, AgentReply, ToolCall
from app.tools import draft_inquiry, faq_search

NO_FAQ_MESSAGE = (
    "FAQ では解決できませんでした。問い合わせとして登録すると、ヘルプデスクの担当者が対応します。"
)
NO_CONTENT_MESSAGE = (
    "問い合わせとして登録できます。困っている内容（いつ・何が・どうなるか）を入力してください。"
)
DRAFT_GUIDE = "内容を確認し、「内容を確認して登録へ」から登録画面で登録してください（まだ登録されていません）。"


class RuleBasedAgent:
    def __init__(self, faq_limit: int = faq_search.DEFAULT_LIMIT) -> None:
        self.faq_limit = faq_limit

    def respond(self, session: Session, message: str) -> AgentReply:
        wants_inquiry = draft_inquiry.has_registration_request(message)
        content = draft_inquiry.strip_registration_request(message) if wants_inquiry else message

        tool_calls: list[ToolCall] = []
        matches = []
        if content:
            tool_calls.append(
                ToolCall(name=faq_search.NAME, arguments={"query": content, "limit": self.faq_limit})
            )
            matches = faq_search.search_faq_tool(session, content, limit=self.faq_limit)

        if matches and not wants_inquiry:
            return self._faq_answer(matches, tool_calls)

        tool_calls.append(ToolCall(name=draft_inquiry.NAME, arguments={"message": message}))
        draft = draft_inquiry.draft_inquiry_tool(message)
        if draft is None:
            return AgentReply(
                message=NO_CONTENT_MESSAGE if wants_inquiry else NO_FAQ_MESSAGE,
                action=AgentAction.INQUIRY_SUGGESTED,
                matched_faqs=matches,
                tool_calls=tool_calls,
            )

        if wants_inquiry:
            lines = ["問い合わせの起票案を作成しました。", DRAFT_GUIDE]
            if matches:
                lines += ["", "関連する FAQ もあります。登録の前にご確認ください。"]
        else:
            lines = ["FAQ では解決できませんでした。問い合わせの起票案を作成しました。", DRAFT_GUIDE]
        return AgentReply(
            message="\n".join(lines),
            action=AgentAction.INQUIRY_DRAFTED,
            matched_faqs=matches,
            tool_calls=tool_calls,
            inquiry_draft=draft,
        )

    @staticmethod
    def _faq_answer(matches, tool_calls) -> AgentReply:  # type: ignore[no-untyped-def]
        top = matches[0].faq
        lines = [f"「{top.question}」の FAQ が見つかりました。", "", top.answer]
        if len(matches) > 1:
            lines += ["", "関連する FAQ:"]
            lines += [f"・{match.faq.question}" for match in matches[1:]]
        lines += ["", "解決しない場合は、問い合わせとして登録できます。"]
        return AgentReply(
            message="\n".join(lines),
            action=AgentAction.FAQ_ANSWER,
            matched_faqs=matches,
            tool_calls=tool_calls,
        )

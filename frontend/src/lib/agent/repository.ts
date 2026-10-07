/**
 * AI Agent（FastAPI の POST /agent/chat）のアクセス層。
 * Server Action からのみ呼び出す（ブラウザから FastAPI へは直接アクセスしない）。
 */
import "server-only";
import { ApiError, ensureOk, readJson, request } from "@/lib/api/http";
import { isInquiryCategory } from "@/lib/inquiries/validation";
import { AGENT_ACTIONS } from "./types";
import type { AgentAction, AgentChatResponse, AgentFaq, AgentToolCall } from "./types";

/** Agent に質問を送り、応答を返す。API の失敗・不正な応答は例外（呼び出し側で利用者向けの文言にする） */
export async function sendAgentMessage(message: string): Promise<AgentChatResponse> {
  const response = await request("POST", "/agent/chat", { body: { message } });
  ensureOk(response, "POST /agent/chat");
  const body = await readJson(response);
  if (!isAgentChatResponse(body)) {
    throw new ApiError(response.status, "Unexpected agent response shape in API response");
  }
  return {
    message: body.message,
    action: body.action,
    matchedFaqs: body.matchedFaqs.map(toAgentFaq),
    toolCalls: body.toolCalls.map(toAgentToolCall),
  };
}

// --- API レスポンスの検証（API は別プロセスのため信頼の境界として形を確認する） ---------

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isAgentAction(value: unknown): value is AgentAction {
  return typeof value === "string" && (AGENT_ACTIONS as readonly string[]).includes(value);
}

function isAgentFaq(value: unknown): value is AgentFaq {
  return (
    isRecord(value) &&
    typeof value.id === "number" &&
    Number.isSafeInteger(value.id) &&
    typeof value.question === "string" &&
    typeof value.answer === "string" &&
    isInquiryCategory(value.category) &&
    typeof value.score === "number"
  );
}

function isAgentToolCall(value: unknown): value is AgentToolCall {
  return isRecord(value) && typeof value.name === "string" && isRecord(value.arguments);
}

function isAgentChatResponse(value: unknown): value is AgentChatResponse {
  return (
    isRecord(value) &&
    typeof value.message === "string" &&
    isAgentAction(value.action) &&
    Array.isArray(value.matchedFaqs) &&
    value.matchedFaqs.every(isAgentFaq) &&
    Array.isArray(value.toolCalls) &&
    value.toolCalls.every(isAgentToolCall)
  );
}

/** 想定外の項目を画面へ渡さないよう、必要な項目だけを取り出す */
function toAgentFaq(faq: AgentFaq): AgentFaq {
  return {
    id: faq.id,
    question: faq.question,
    answer: faq.answer,
    category: faq.category,
    score: faq.score,
  };
}

function toAgentToolCall(call: AgentToolCall): AgentToolCall {
  return { name: call.name, arguments: call.arguments };
}

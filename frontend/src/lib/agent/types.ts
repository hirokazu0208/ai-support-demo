import type { InquiryCategory } from "@/lib/inquiries/types";

/** AI Agent との対話（FastAPI の POST /agent/chat）に対応する型 */

export const AGENT_ACTIONS = ["FAQ_ANSWER", "INQUIRY_SUGGESTED"] as const;
/** FAQ_ANSWER: FAQ をもとに回答 / INQUIRY_SUGGESTED: FAQ で解決できず問い合わせ登録を提案 */
export type AgentAction = (typeof AGENT_ACTIONS)[number];

/** backend の FaqResponse（GET /faqs と同じ形） */
export type AgentFaq = {
  id: number;
  question: string;
  answer: string;
  category: InquiryCategory;
  score: number;
};

/** Agent が呼び出した Tool（例: search_faqs） */
export type AgentToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

/** backend の AgentChatResponse（JSON は camelCase） */
export type AgentChatResponse = {
  message: string;
  action: AgentAction;
  matchedFaqs: AgentFaq[];
  toolCalls: AgentToolCall[];
};

/** backend の AgentChatRequest.message と同じ上限（前後の空白を除いたコードポイント数） */
export const AGENT_MESSAGE_MAX_LENGTH = 1000;

/** 画面上の会話の 1 件（会話はブラウザ上の状態にのみ保持し、DB には保存しない） */
export type ChatEntry =
  | { id: string; role: "user"; text: string }
  | ({ id: string; role: "agent" } & AgentChatResponse);

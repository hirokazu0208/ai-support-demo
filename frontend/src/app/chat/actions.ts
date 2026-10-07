"use server";

import { sendAgentMessage } from "@/lib/agent/repository";
import { AGENT_MESSAGE_MAX_LENGTH } from "@/lib/agent/types";
import type { ChatEntry } from "@/lib/agent/types";

/** チャット画面（useActionState）と Server Action の間でやり取りする状態 */
export type ChatState = {
  entries: ChatEntry[];
  /** 送信できなかった場合のエラー（利用者向けの文言のみ） */
  error?: string;
  /** エラー時に入力欄へ戻す値 */
  draft?: string;
};

/** 画面に保持する会話の上限（古いものから捨てる） */
const MAX_ENTRIES = 40;

const CONNECTION_ERROR_MESSAGE =
  "AIサポートに接続できませんでした。時間をおいて再度お試しください。";

/**
 * 利用者のメッセージを Agent（FastAPI の POST /agent/chat）へ送り、会話に追加する。
 * ブラウザは FastAPI を直接呼ばず、この Server Action（Next.js のサーバー側）が呼び出す。
 * 会話履歴は画面の状態として受け渡すだけで、サーバー側では保存しない。
 */
export async function sendChatMessageAction(
  prevState: ChatState,
  formData: FormData,
): Promise<ChatState> {
  const entries = Array.isArray(prevState?.entries) ? prevState.entries : [];
  const raw = formData.get("message");
  const message = typeof raw === "string" ? raw.trim() : "";

  if (!message) {
    return { entries, error: "メッセージを入力してください" };
  }
  if ([...message].length > AGENT_MESSAGE_MAX_LENGTH) {
    return {
      entries,
      error: `メッセージは${AGENT_MESSAGE_MAX_LENGTH}文字以内で入力してください`,
      draft: message,
    };
  }

  try {
    const reply = await sendAgentMessage(message);
    const next: ChatEntry[] = [
      ...entries,
      { id: crypto.randomUUID(), role: "user", text: message },
      { id: crypto.randomUUID(), role: "agent", ...reply },
    ];
    return { entries: next.slice(-MAX_ENTRIES) };
  } catch (error) {
    // 原因（接続失敗・API のエラー・不正な応答）はサーバーのログにのみ出力し、利用者には定型文を返す
    console.error("[chat] Agent API の呼び出しに失敗しました", error);
    return { entries, error: CONNECTION_ERROR_MESSAGE, draft: message };
  }
}

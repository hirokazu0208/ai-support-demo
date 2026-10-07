"use client";

import { useActionState, useEffect, useRef } from "react";
import { sendChatMessageAction } from "@/app/chat/actions";
import type { ChatState } from "@/app/chat/actions";
import { AGENT_MESSAGE_MAX_LENGTH } from "@/lib/agent/types";
import { AgentMessage } from "./AgentMessage";

const initialState: ChatState = { entries: [] };

/**
 * AI サポートのチャット。送信は Server Action（Next.js のサーバー側から FastAPI を呼ぶ）で行い、
 * 会話はこの画面の状態にのみ保持する（再読み込みで消える）。
 */
export function ChatPanel() {
  const [state, formAction, pending] = useActionState(
    sendChatMessageAction,
    initialState,
  );
  const endRef = useRef<HTMLDivElement>(null);

  // 新しいメッセージが届いたら最下部まで表示する
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [state.entries.length]);

  return (
    <div className="flex flex-col gap-4">
      <ol
        aria-label="会話"
        aria-live="polite"
        className="flex flex-col gap-4"
      >
        {state.entries.length === 0 && (
          <li className="rounded-md border border-dashed border-zinc-300 px-4 py-6 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
            困っていることを入力してください。AI が FAQ を検索して回答します。
            <br />
            例: 「VPNがすぐ切れます」「パスワードを忘れました」
          </li>
        )}
        {state.entries.map((entry) =>
          entry.role === "user" ? (
            <li key={entry.id} className="flex flex-col items-end gap-1">
              <span className="text-xs text-zinc-500">あなた</span>
              <p className="max-w-[85%] whitespace-pre-wrap rounded-lg bg-foreground px-4 py-2 text-sm text-background">
                {entry.text}
              </p>
            </li>
          ) : (
            <li key={entry.id} className="flex flex-col items-start gap-1">
              <span className="text-xs text-zinc-500">AI サポート</span>
              <div className="w-full max-w-[85%] rounded-lg bg-zinc-100 px-4 py-3 dark:bg-zinc-900">
                <AgentMessage reply={entry} />
              </div>
            </li>
          ),
        )}
        {pending && (
          <li className="text-sm text-zinc-500" aria-busy="true">
            AI サポートが回答を作成しています…
          </li>
        )}
      </ol>
      <div ref={endRef} />

      {/* 送信後に React がフォームをリセットするため、エラーで戻した入力値が変わったら再マウントする */}
      <form
        key={state.draft ?? ""}
        action={formAction}
        className="flex flex-col gap-2 border-t border-zinc-200 pt-4 dark:border-zinc-800"
      >
        {state.error && (
          <p
            role="alert"
            className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
          >
            {state.error}
          </p>
        )}
        <label htmlFor="message" className="text-sm font-medium">
          メッセージ
        </label>
        <div className="flex gap-2">
          <textarea
            id="message"
            name="message"
            required
            rows={2}
            maxLength={AGENT_MESSAGE_MAX_LENGTH}
            defaultValue={state.draft}
            placeholder="例: VPNがすぐ切れます"
            className="flex-1 rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-700"
          />
          <button
            type="submit"
            disabled={pending}
            className="self-end rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? "送信中…" : "送信"}
          </button>
        </div>
      </form>
    </div>
  );
}

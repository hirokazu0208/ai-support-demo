import type { Metadata } from "next";
import { ChatPanel } from "@/components/chat/ChatPanel";

export const metadata: Metadata = {
  title: "AIサポート | AI Support Desk",
};

export default function ChatPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">AIサポート</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          AI が FAQ を検索して回答します。解決しない場合は問い合わせとして登録できます。
        </p>
      </div>
      <ChatPanel />
    </div>
  );
}

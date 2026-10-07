import Link from "next/link";
import type { AgentChatResponse } from "@/lib/agent/types";
import { FaqCard } from "./FaqCard";
import { InquiryDraftCard } from "./InquiryDraftCard";

/** Agent の応答（回答・参照した FAQ・起票案・利用した Tool・次の操作） */
export function AgentMessage({ reply }: { reply: AgentChatResponse }) {
  const toolNames = reply.toolCalls.map((call) => call.name);

  return (
    <div className="flex flex-col gap-3">
      <p className="whitespace-pre-wrap text-sm">{reply.message}</p>

      {reply.matchedFaqs.length > 0 && (
        <section aria-label="参照した FAQ" className="flex flex-col gap-2">
          {reply.matchedFaqs.map((faq) => (
            <FaqCard key={faq.id} faq={faq} />
          ))}
        </section>
      )}

      {reply.inquiryDraft && <InquiryDraftCard draft={reply.inquiryDraft} />}

      {reply.action === "INQUIRY_SUGGESTED" && (
        // 起票案を作れなかった場合（内容がない等）は、空の登録画面へ案内する
        <div>
          <Link
            href="/inquiries/new"
            className="inline-block rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80"
          >
            問い合わせを登録する
          </Link>
        </div>
      )}

      {toolNames.length > 0 && (
        <p className="text-xs text-zinc-500">
          使用した Tool: <code className="font-mono">{toolNames.join(", ")}</code>
        </p>
      )}
    </div>
  );
}

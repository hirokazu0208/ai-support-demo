import type { AgentFaq } from "@/lib/agent/types";
import { INQUIRY_CATEGORY_LABELS } from "@/lib/inquiries/types";

/** Agent が参照した FAQ（FAQ 検索 Tool の結果） */
export function FaqCard({ faq }: { faq: AgentFaq }) {
  return (
    <article className="rounded-md border border-zinc-200 bg-background px-4 py-3 dark:border-zinc-800">
      <h3 className="text-sm font-semibold">{faq.question}</h3>
      <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">
        {faq.answer}
      </p>
      <p className="mt-2 flex gap-3 text-xs text-zinc-500">
        <span>カテゴリ: {INQUIRY_CATEGORY_LABELS[faq.category]}</span>
        <span>一致度: {faq.score}</span>
      </p>
    </article>
  );
}

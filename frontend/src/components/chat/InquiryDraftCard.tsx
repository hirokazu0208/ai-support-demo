import Link from "next/link";
import type { InquiryDraft } from "@/lib/agent/types";
import { INQUIRY_CATEGORY_LABELS } from "@/lib/inquiries/types";

/**
 * Agent が作成した問い合わせの起票案。ここでは登録しない（Human-in-the-loop）。
 * 「内容を確認して登録へ」で既存の登録画面へ値を引き継ぎ、人が確認・修正してから登録する。
 */
export function InquiryDraftCard({ draft }: { draft: InquiryDraft }) {
  const params = new URLSearchParams({
    title: draft.title,
    category: draft.category,
    description: draft.description,
  });

  return (
    <section
      aria-label="問い合わせ起票案"
      className="flex flex-col gap-3 rounded-md border border-zinc-300 bg-background px-4 py-3 dark:border-zinc-700"
    >
      <h3 className="text-sm font-semibold">問い合わせ起票案</h3>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-zinc-500">タイトル</dt>
        <dd>{draft.title}</dd>
        <dt className="text-zinc-500">カテゴリ</dt>
        <dd>{INQUIRY_CATEGORY_LABELS[draft.category]}</dd>
        <dt className="text-zinc-500">内容</dt>
        <dd className="whitespace-pre-wrap">{draft.description}</dd>
      </dl>
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={`/inquiries/new?${params.toString()}`}
          className="inline-block rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80"
        >
          内容を確認して登録へ
        </Link>
        <span className="text-xs text-zinc-500">まだ登録されていません</span>
      </div>
    </section>
  );
}

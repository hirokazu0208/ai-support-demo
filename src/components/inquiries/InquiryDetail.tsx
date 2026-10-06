import { formatDateTime } from "@/lib/inquiries/format";
import { INQUIRY_CATEGORY_LABELS } from "@/lib/inquiries/types";
import type { Inquiry } from "@/lib/inquiries/types";
import { StatusBadge } from "./StatusBadge";

export function InquiryDetail({ inquiry }: { inquiry: Inquiry }) {
  return (
    <article className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">{inquiry.title}</h1>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
        <dt className="font-medium text-zinc-600 dark:text-zinc-400">
          ステータス
        </dt>
        <dd>
          <StatusBadge status={inquiry.status} />
        </dd>
        <dt className="font-medium text-zinc-600 dark:text-zinc-400">
          カテゴリ
        </dt>
        <dd>{INQUIRY_CATEGORY_LABELS[inquiry.category]}</dd>
        <dt className="font-medium text-zinc-600 dark:text-zinc-400">
          作成日時
        </dt>
        <dd>
          <time dateTime={inquiry.createdAt}>
            {formatDateTime(inquiry.createdAt)}
          </time>
        </dd>
      </dl>
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">問い合わせ内容</h2>
        <p className="whitespace-pre-wrap leading-7">{inquiry.description}</p>
      </section>
    </article>
  );
}

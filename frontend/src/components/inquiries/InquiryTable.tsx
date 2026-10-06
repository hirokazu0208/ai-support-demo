import Link from "next/link";
import { formatDateTime } from "@/lib/inquiries/format";
import { INQUIRY_CATEGORY_LABELS } from "@/lib/inquiries/types";
import type { Inquiry } from "@/lib/inquiries/types";
import { StatusBadge } from "./StatusBadge";

export function InquiryTable({ inquiries }: { inquiries: Inquiry[] }) {
  if (inquiries.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-zinc-300 px-4 py-12 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:text-zinc-400">
        該当する問い合わせはありません
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="bg-zinc-50 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">
              タイトル
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              カテゴリ
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              ステータス
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              作成日時
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {inquiries.map((inquiry) => (
            <tr key={inquiry.id}>
              <td className="px-4 py-3 font-medium">
                <Link
                  href={`/inquiries/${inquiry.id}`}
                  className="hover:underline"
                >
                  {inquiry.title}
                </Link>
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                {INQUIRY_CATEGORY_LABELS[inquiry.category]}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={inquiry.status} />
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-zinc-600 dark:text-zinc-400">
                <time dateTime={inquiry.createdAt}>
                  {formatDateTime(inquiry.createdAt)}
                </time>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

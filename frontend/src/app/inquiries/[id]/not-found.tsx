import Link from "next/link";

export default function InquiryNotFound() {
  return (
    <div className="flex flex-col items-start gap-4">
      <h1 className="text-2xl font-semibold">問い合わせが見つかりません</h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        指定された問い合わせは存在しないか、削除された可能性があります。
      </p>
      <Link
        href="/inquiries"
        className="text-sm text-zinc-600 underline hover:text-foreground dark:text-zinc-400"
      >
        ← 一覧へ戻る
      </Link>
    </div>
  );
}

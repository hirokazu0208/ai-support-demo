import type { Metadata } from "next";
import Link from "next/link";
import { InquiryForm } from "@/components/inquiries/InquiryForm";
import { parseInquiryPrefill } from "@/lib/inquiries/validation";

export const metadata: Metadata = {
  title: "新規問い合わせ | AI Support Desk",
};

export default async function NewInquiryPage({
  searchParams,
}: PageProps<"/inquiries/new">) {
  // AIサポートの起票案がクエリにある場合のみ初期値にする（登録は「登録する」を押したときだけ）
  const prefill = parseInquiryPrefill(await searchParams);

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/inquiries"
        className="text-sm text-zinc-600 underline hover:text-foreground dark:text-zinc-400"
      >
        ← 一覧へ戻る
      </Link>
      <h1 className="text-2xl font-semibold">新規問い合わせ</h1>
      {prefill && (
        <p
          role="status"
          className="rounded-md bg-zinc-100 px-4 py-3 text-sm dark:bg-zinc-900"
        >
          AIサポートが作成した起票案を入力しました。内容を確認・修正してから「登録する」を押してください（まだ登録されていません）。
        </p>
      )}
      <InquiryForm defaultValues={prefill} />
    </div>
  );
}

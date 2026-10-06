import type { Metadata } from "next";
import Link from "next/link";
import { InquiryForm } from "@/components/inquiries/InquiryForm";

export const metadata: Metadata = {
  title: "新規問い合わせ | AI Support Desk",
};

export default function NewInquiryPage() {
  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/inquiries"
        className="text-sm text-zinc-600 underline hover:text-foreground dark:text-zinc-400"
      >
        ← 一覧へ戻る
      </Link>
      <h1 className="text-2xl font-semibold">新規問い合わせ</h1>
      <InquiryForm />
    </div>
  );
}

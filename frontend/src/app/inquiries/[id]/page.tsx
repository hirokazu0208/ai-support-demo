import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { InquiryDetail } from "@/components/inquiries/InquiryDetail";
import { InquiryStatusForm } from "@/components/inquiries/InquiryStatusForm";
import { getInquiryById } from "@/lib/inquiries/repository";

export const metadata: Metadata = {
  title: "問い合わせ詳細 | AI Support Desk",
};

export default async function InquiryDetailPage({
  params,
}: PageProps<"/inquiries/[id]">) {
  const { id } = await params;
  const inquiry = await getInquiryById(id);

  if (!inquiry) {
    notFound();
  }

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/inquiries"
        className="text-sm text-zinc-600 underline hover:text-foreground dark:text-zinc-400"
      >
        ← 一覧へ戻る
      </Link>
      <InquiryDetail inquiry={inquiry} />
      <InquiryStatusForm id={inquiry.id} currentStatus={inquiry.status} />
    </div>
  );
}

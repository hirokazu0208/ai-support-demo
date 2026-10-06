import type { Metadata } from "next";
import Link from "next/link";
import { InquirySearchForm } from "@/components/inquiries/InquirySearchForm";
import { InquiryTable } from "@/components/inquiries/InquiryTable";
import { getInquiries } from "@/lib/inquiries/repository";
import { parseInquiryQuery } from "@/lib/inquiries/validation";

export const metadata: Metadata = {
  title: "問い合わせ一覧 | AI Support Desk",
};

export default async function InquiriesPage({
  searchParams,
}: PageProps<"/inquiries">) {
  const query = parseInquiryQuery(await searchParams);
  const inquiries = await getInquiries(query);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">問い合わせ一覧</h1>
        <Link
          href="/inquiries/new"
          className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80"
        >
          新規問い合わせ
        </Link>
      </div>
      <InquirySearchForm q={query.q} status={query.status} />
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        {inquiries.length}件
      </p>
      <InquiryTable inquiries={inquiries} />
    </div>
  );
}

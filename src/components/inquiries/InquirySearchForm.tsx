import Form from "next/form";
import Link from "next/link";
import { INQUIRY_STATUSES, INQUIRY_STATUS_LABELS } from "@/lib/inquiries/types";
import type { InquiryQuery } from "@/lib/inquiries/types";

/** 検索条件は URL（?q=&status=）で管理する GET フォーム */
export function InquirySearchForm({ q, status }: InquiryQuery) {
  return (
    // key により、戻る/進むで URL が変わったときも入力欄を URL の値に合わせる
    <Form
      key={`${q ?? ""}|${status ?? ""}`}
      action="/inquiries"
      className="flex flex-col gap-3 sm:flex-row sm:items-end"
    >
      <label className="flex flex-1 flex-col gap-1 text-sm">
        <span className="font-medium">キーワード</span>
        <input
          type="search"
          name="q"
          defaultValue={q}
          placeholder="タイトル・内容で検索"
          className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">ステータス</span>
        <select
          name="status"
          defaultValue={status ?? ""}
          className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700"
        >
          <option value="">すべて</option>
          {INQUIRY_STATUSES.map((value) => (
            <option key={value} value={value}>
              {INQUIRY_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
      </label>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80"
        >
          検索
        </button>
        <Link
          href="/inquiries"
          className="text-sm text-zinc-600 underline hover:text-foreground dark:text-zinc-400"
        >
          クリア
        </Link>
      </div>
    </Form>
  );
}

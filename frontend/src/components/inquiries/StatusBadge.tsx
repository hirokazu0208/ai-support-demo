import { INQUIRY_STATUS_LABELS } from "@/lib/inquiries/types";
import type { InquiryStatus } from "@/lib/inquiries/types";

const STATUS_STYLES: Record<InquiryStatus, string> = {
  OPEN: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  IN_PROGRESS:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  CLOSED: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

export function StatusBadge({ status }: { status: InquiryStatus }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {INQUIRY_STATUS_LABELS[status]}
    </span>
  );
}

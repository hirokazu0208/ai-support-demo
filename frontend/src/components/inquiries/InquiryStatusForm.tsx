"use client";

import { useActionState } from "react";
import { updateInquiryStatusAction } from "@/app/inquiries/actions";
import { INQUIRY_STATUSES, INQUIRY_STATUS_LABELS } from "@/lib/inquiries/types";
import type { InquiryStatus } from "@/lib/inquiries/types";
import type { UpdateInquiryStatusFormState } from "@/lib/inquiries/validation";

const initialState: UpdateInquiryStatusFormState = {};

export function InquiryStatusForm({
  id,
  currentStatus,
}: {
  id: string;
  currentStatus: InquiryStatus;
}) {
  // id は bind ではなく hidden input で渡す。bind は描画ごとに新しい参照を作るため、
  // JS 無効時の送信後のサーバー描画で useActionState が再描画を繰り返し停止しなくなる
  const [state, formAction, pending] = useActionState(
    updateInquiryStatusAction,
    initialState,
  );

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">ステータス変更</h2>
      {/* 送信後に React がフォームをリセットするため、更新後のステータスが
          届いたら再マウントして select の初期値に反映する */}
      <form
        key={currentStatus}
        action={formAction}
        className="flex flex-wrap items-center gap-3"
      >
        <input type="hidden" name="id" value={id} />
        <label htmlFor="status" className="sr-only">
          ステータス
        </label>
        <select
          id="status"
          name="status"
          defaultValue={currentStatus}
          className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-700"
        >
          {INQUIRY_STATUSES.map((value) => (
            <option key={value} value={value}>
              {INQUIRY_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "更新中…" : "更新"}
        </button>
      </form>
      {state.error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {state.error}
        </p>
      )}
      {state.message && (
        <p role="status" className="text-sm text-green-700 dark:text-green-400">
          {state.message}
        </p>
      )}
    </section>
  );
}

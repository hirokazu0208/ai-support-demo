"use client";

import { useActionState } from "react";
import { createInquiryAction } from "@/app/inquiries/actions";
import {
  INQUIRY_CATEGORIES,
  INQUIRY_CATEGORY_LABELS,
} from "@/lib/inquiries/types";
import {
  DESCRIPTION_MAX_LENGTH,
  TITLE_MAX_LENGTH,
} from "@/lib/inquiries/validation";
import type {
  CreateInquiryFormState,
  CreateInquiryFormValues,
} from "@/lib/inquiries/validation";

const initialState: CreateInquiryFormState = {};

const inputClassName =
  "rounded-md border border-zinc-300 bg-transparent px-3 py-2 aria-invalid:border-red-500 dark:border-zinc-700";

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) {
    return null;
  }
  return (
    <p id={id} className="text-sm text-red-600 dark:text-red-400">
      {message}
    </p>
  );
}

/** defaultValues: 初期値（AIサポートの起票案）。送信後は Server Action が返した入力値を優先する */
export function InquiryForm({
  defaultValues,
}: {
  defaultValues?: CreateInquiryFormValues;
}) {
  const [state, formAction, pending] = useActionState(
    createInquiryAction,
    initialState,
  );
  const { errors } = state;
  const values = state.values ?? defaultValues;

  return (
    // 送信後に React がフォームをリセットするため、返却された入力値が変わったら
    // 再マウントして defaultValue に反映し、エラー時も入力内容を保持する
    <form
      key={JSON.stringify(values ?? {})}
      action={formAction}
      className="flex flex-col gap-5"
    >
      {state.formError && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300"
        >
          {state.formError}
        </p>
      )}

      <div className="flex flex-col gap-1">
        <label htmlFor="title" className="text-sm font-medium">
          タイトル
        </label>
        <input
          id="title"
          name="title"
          type="text"
          required
          maxLength={TITLE_MAX_LENGTH}
          defaultValue={values?.title}
          aria-invalid={errors?.title ? true : undefined}
          aria-describedby={errors?.title ? "title-error" : undefined}
          className={inputClassName}
        />
        <FieldError id="title-error" message={errors?.title} />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="category" className="text-sm font-medium">
          カテゴリ
        </label>
        <select
          id="category"
          name="category"
          required
          defaultValue={values?.category ?? ""}
          aria-invalid={errors?.category ? true : undefined}
          aria-describedby={errors?.category ? "category-error" : undefined}
          className={`${inputClassName} sm:max-w-xs`}
        >
          <option value="">選択してください</option>
          {INQUIRY_CATEGORIES.map((value) => (
            <option key={value} value={value}>
              {INQUIRY_CATEGORY_LABELS[value]}
            </option>
          ))}
        </select>
        <FieldError id="category-error" message={errors?.category} />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="description" className="text-sm font-medium">
          問い合わせ内容
        </label>
        <textarea
          id="description"
          name="description"
          required
          rows={8}
          maxLength={DESCRIPTION_MAX_LENGTH}
          defaultValue={values?.description}
          aria-invalid={errors?.description ? true : undefined}
          aria-describedby={
            errors?.description ? "description-error" : undefined
          }
          className={inputClassName}
        />
        <FieldError id="description-error" message={errors?.description} />
      </div>

      <div>
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "登録中…" : "登録する"}
        </button>
      </div>
    </form>
  );
}

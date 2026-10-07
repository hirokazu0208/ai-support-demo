import { INQUIRY_CATEGORIES, INQUIRY_STATUSES } from "./types";
import type {
  CreateInquiryInput,
  InquiryCategory,
  InquiryQuery,
  InquiryStatus,
} from "./types";

type SearchParams = Record<string, string | string[] | undefined>;

export const TITLE_MAX_LENGTH = 100;
export const DESCRIPTION_MAX_LENGTH = 2000;
/** 検索キーワードの上限（FastAPI の GET /inquiries の q と同じ） */
export const QUERY_MAX_LENGTH = 200;

export function isInquiryStatus(value: unknown): value is InquiryStatus {
  return (
    typeof value === "string" &&
    (INQUIRY_STATUSES as readonly string[]).includes(value)
  );
}

export function isInquiryCategory(value: unknown): value is InquiryCategory {
  return (
    typeof value === "string" &&
    (INQUIRY_CATEGORIES as readonly string[]).includes(value)
  );
}

/** 同名パラメータが複数ある場合は先頭の値を採用する */
function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * URL の searchParams を InquiryQuery に変換する。
 * 空文字・未知の status は「指定なし」として扱う。
 * q は QUERY_MAX_LENGTH 文字（コードポイント単位）までに切り詰める（API が超過を 422 にするため）。
 */
export function parseInquiryQuery(searchParams: SearchParams): InquiryQuery {
  const rawQ = firstValue(searchParams.q)?.trim();
  const q = rawQ && truncateChars(rawQ, QUERY_MAX_LENGTH).trim();
  const status = firstValue(searchParams.status);

  return {
    q: q || undefined,
    status: isInquiryStatus(status) ? status : undefined,
  };
}

type CreateInquiryField = keyof CreateInquiryInput;

/** フォームに再表示する入力値（未加工の文字列） */
export type CreateInquiryFormValues = Record<CreateInquiryField, string>;

export type CreateInquiryFieldErrors = Partial<
  Record<CreateInquiryField, string>
>;

/** 登録フォーム（useActionState）と Server Action の間でやり取りする状態 */
export type CreateInquiryFormState = {
  errors?: CreateInquiryFieldErrors;
  /** 項目に紐づかないエラー（登録処理自体の失敗など） */
  formError?: string;
  values?: CreateInquiryFormValues;
};

export type CreateInquiryParseResult =
  | { success: true; data: CreateInquiryInput }
  | {
      success: false;
      errors: CreateInquiryFieldErrors;
      values: CreateInquiryFormValues;
    };

/** 文字列以外（ファイル・未送信）は空文字として扱い、必須エラーにする */
function textValue(formData: FormData, name: CreateInquiryField): string {
  const value = formData.get(name);
  return typeof value === "string" ? value : "";
}

/** 文字数はコードポイント単位で数える（Python の len() と同じ数え方） */
function countChars(value: string): number {
  return [...value].length;
}

/** コードポイント単位で先頭から maxLength 文字に切り詰める（サロゲートペアを分割しない） */
function truncateChars(value: string, maxLength: number): string {
  const chars = [...value];
  return chars.length > maxLength ? chars.slice(0, maxLength).join("") : value;
}

/**
 * 新規登録フォームの FormData を検証し、CreateInquiryInput に変換する。
 * title・description は前後の空白を除いた値で判定・登録する。
 */
export function parseCreateInquiryInput(
  formData: FormData,
): CreateInquiryParseResult {
  const values: CreateInquiryFormValues = {
    title: textValue(formData, "title"),
    category: textValue(formData, "category"),
    description: textValue(formData, "description"),
  };
  const title = values.title.trim();
  const description = values.description.trim();
  const category = isInquiryCategory(values.category) ? values.category : null;
  const errors: CreateInquiryFieldErrors = {};

  if (!title) {
    errors.title = "タイトルを入力してください";
  } else if (countChars(title) > TITLE_MAX_LENGTH) {
    errors.title = `タイトルは${TITLE_MAX_LENGTH}文字以内で入力してください`;
  }

  if (!category) {
    errors.category = "カテゴリを選択してください";
  }

  if (!description) {
    errors.description = "問い合わせ内容を入力してください";
  } else if (countChars(description) > DESCRIPTION_MAX_LENGTH) {
    errors.description = `問い合わせ内容は${DESCRIPTION_MAX_LENGTH}文字以内で入力してください`;
  }

  if (!category || Object.keys(errors).length > 0) {
    return { success: false, errors, values };
  }

  return { success: true, data: { title, category, description } };
}

/** ステータス変更フォーム（useActionState）と Server Action の間でやり取りする状態 */
export type UpdateInquiryStatusFormState = {
  message?: string;
  error?: string;
};

export type InquiryStatusUpdateParseResult =
  | { success: true; id: string; status: InquiryStatus }
  | { success: false; error: string };

/**
 * ステータス変更フォームの FormData（hidden の id と status）を検証する。
 * id の存在確認は repository の戻り値で行う。
 */
export function parseInquiryStatusUpdate(
  formData: FormData,
): InquiryStatusUpdateParseResult {
  const id = formData.get("id");
  if (typeof id !== "string" || !id) {
    return { success: false, error: "問い合わせが見つかりません" };
  }
  const status = formData.get("status");
  if (!isInquiryStatus(status)) {
    return { success: false, error: "ステータスを選択してください" };
  }
  return { success: true, id, status };
}

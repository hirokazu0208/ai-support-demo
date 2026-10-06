import { INQUIRY_STATUSES } from "./types";
import type { InquiryQuery, InquiryStatus } from "./types";

type SearchParams = Record<string, string | string[] | undefined>;

export function isInquiryStatus(value: unknown): value is InquiryStatus {
  return (
    typeof value === "string" &&
    (INQUIRY_STATUSES as readonly string[]).includes(value)
  );
}

/** 同名パラメータが複数ある場合は先頭の値を採用する */
function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * URL の searchParams を InquiryQuery に変換する。
 * 空文字・未知の status は「指定なし」として扱う。
 */
export function parseInquiryQuery(searchParams: SearchParams): InquiryQuery {
  const q = firstValue(searchParams.q)?.trim();
  const status = firstValue(searchParams.status);

  return {
    q: q || undefined,
    status: isInquiryStatus(status) ? status : undefined,
  };
}

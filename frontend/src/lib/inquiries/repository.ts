/**
 * 問い合わせデータのアクセス層。
 *
 * UI・Server Actions はこのモジュールの関数だけを呼び出す。
 * Demo 2 では FastAPI の REST API を Next.js のサーバー側から呼び出す
 * （ブラウザから FastAPI へは直接アクセスしない）。
 *
 *   getInquiries        -> GET   /inquiries?q=&status=
 *   getInquiryById      -> GET   /inquiries/{id}           （404 → null）
 *   createInquiry       -> POST  /inquiries
 *   updateInquiryStatus -> PATCH /inquiries/{id}/status    （404 → null）
 *
 * HTTP の共通処理（API_BASE_URL・タイムアウト・no-store・エラー処理）は src/lib/api/http.ts にある。
 */
import "server-only";
import { ApiError, ensureOk, readJson, request } from "@/lib/api/http";
import type {
  CreateInquiryInput,
  Inquiry,
  InquiryQuery,
  InquiryStatus,
} from "./types";
import { isInquiryCategory, isInquiryStatus } from "./validation";

/** backend の id の上限（PostgreSQL の SERIAL = int4 の最大値） */
const MAX_INQUIRY_ID = 2_147_483_647;

/** 問い合わせ一覧を作成日時の新しい順（同時刻は id の降順）で返す */
export async function getInquiries(
  query: InquiryQuery = {},
): Promise<Inquiry[]> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.status) params.set("status", query.status);

  const response = await request("GET", "/inquiries", { params });
  ensureOk(response, "GET /inquiries");
  const body = await readJson(response);
  if (!Array.isArray(body)) {
    throw new ApiError(response.status, "GET /inquiries: response is not an array");
  }
  return body.map(toInquiry);
}

/** 該当なし・不正な id の場合は null（詳細画面は notFound() で 404 を表示する） */
export async function getInquiryById(id: string): Promise<Inquiry | null> {
  if (!isValidInquiryId(id)) {
    return null;
  }

  const response = await request("GET", `/inquiries/${id}`);
  if (response.status === 404) {
    return null;
  }
  ensureOk(response, "GET /inquiries/{id}");
  return toInquiry(await readJson(response));
}

/** id・status・createdAt は API 側で決定する */
export async function createInquiry(
  input: CreateInquiryInput,
): Promise<Inquiry> {
  const response = await request("POST", "/inquiries", {
    body: {
      title: input.title,
      description: input.description,
      category: input.category,
    },
  });
  ensureOk(response, "POST /inquiries");
  return toInquiry(await readJson(response));
}

/** 該当なし・不正な id の場合は null。同じ status への変更も成功（API 側で更新なし） */
export async function updateInquiryStatus(
  id: string,
  status: InquiryStatus,
): Promise<Inquiry | null> {
  if (!isValidInquiryId(id)) {
    return null;
  }

  const response = await request("PATCH", `/inquiries/${id}/status`, {
    body: { status },
  });
  if (response.status === 404) {
    return null;
  }
  ensureOk(response, "PATCH /inquiries/{id}/status");
  return toInquiry(await readJson(response));
}

/**
 * API に渡せる id か。正の整数の正規形（先頭 0 なし）かつ backend の上限以下のみ許可する。
 * "01" を 1 と同一視すると同じ問い合わせに複数の URL ができるため無効とする。
 */
function isValidInquiryId(id: string): boolean {
  return /^[1-9]\d*$/.test(id) && Number(id) <= MAX_INQUIRY_ID;
}

// --- API レスポンス → frontend の型 ----------------------------------------------

/** FastAPI の InquiryResponse（JSON は camelCase、id は integer、日時は UTC の ISO 8601） */
type ApiInquiry = {
  id: number;
  title: string;
  description: string;
  category: Inquiry["category"];
  status: Inquiry["status"];
  createdAt: string;
  updatedAt: string;
};

/**
 * API の JSON を検証して frontend の Inquiry に変換する。
 * id は string に変換し、updatedAt は検証のみ行って画面では使わないため含めない。
 */
function toInquiry(value: unknown): Inquiry {
  if (!isApiInquiry(value)) {
    throw new ApiError(200, "Unexpected inquiry shape in API response");
  }
  return {
    id: String(value.id),
    title: value.title,
    description: value.description,
    category: value.category,
    status: value.status,
    createdAt: value.createdAt,
  };
}

function isApiInquiry(value: unknown): value is ApiInquiry {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === "number" &&
    Number.isSafeInteger(v.id) &&
    v.id > 0 &&
    typeof v.title === "string" &&
    typeof v.description === "string" &&
    isInquiryCategory(v.category) &&
    isInquiryStatus(v.status) &&
    isUtcDateTime(v.createdAt) &&
    isUtcDateTime(v.updatedAt)
  );
}

/** API は UTC の ISO 8601（末尾 Z）で返す */
function isUtcDateTime(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.endsWith("Z") &&
    !Number.isNaN(Date.parse(value))
  );
}

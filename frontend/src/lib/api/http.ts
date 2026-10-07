/**
 * FastAPI（backend）を呼び出す HTTP の共通処理。Next.js のサーバー側（repository）からのみ使う。
 *
 * - API_BASE_URL はサーバー側の環境変数（NEXT_PUBLIC_ を付けない）。ブラウザ向けコードには含めない
 * - API のエラー本文は例外メッセージにも含めない（利用者に内部情報を出さないため）
 */
import "server-only";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

/** API の呼び出しが応答しない場合にページが止まり続けないようにする */
const REQUEST_TIMEOUT_MS = 10_000;

/** API の想定外の応答（404 以外のエラー・不正な JSON・型の不一致） */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type RequestOptions = {
  params?: URLSearchParams;
  body?: unknown;
};

/**
 * API を呼び出す。問い合わせは他の利用者や API から直接変更され得る共有データのため、
 * 常に最新を取得する（cache: "no-store"）。ルートが静的と判定された場合に
 * next build 時の 1 回の取得結果が固定されることも防ぐ。
 */
export async function request(
  method: "GET" | "POST" | "PATCH",
  path: string,
  { params, body }: RequestOptions = {},
): Promise<Response> {
  const query = params?.size ? `?${params}` : "";
  return fetch(`${getApiBaseUrl()}${path}${query}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
}

/**
 * API_BASE_URL（サーバー側のみ。NEXT_PUBLIC_ は付けない）を末尾の / を除いて返す。
 * 未設定・空の場合は既定値。不正な値は例外（呼び出し時に評価し、ビルドや import を失敗させない）。
 */
function getApiBaseUrl(): string {
  const raw = process.env.API_BASE_URL?.trim() || DEFAULT_API_BASE_URL;

  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new Error("API_BASE_URL が不正です（URL として解釈できません）");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("API_BASE_URL が不正です（http: または https: のみ使用できます）");
  }
  if (url.search || url.hash) {
    throw new Error("API_BASE_URL が不正です（? や # は含められません）");
  }
  // new URL(path, base) は base のパス（例: /api）を落とすため、文字列として連結する
  return `${url.origin}${url.pathname.replace(/\/+$/, "")}`;
}

/** 2xx 以外は例外。メッセージにはメソッド・パス・ステータスのみ含め、API の本文は含めない */
export function ensureOk(response: Response, label: string): void {
  if (!response.ok) {
    throw new ApiError(response.status, `${label} failed with status ${response.status}`);
  }
}

export async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new ApiError(response.status, "Invalid JSON in API response");
  }
}

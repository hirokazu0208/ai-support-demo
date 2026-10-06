/**
 * 問い合わせデータのアクセス層。
 *
 * UI・Server Actions はこのモジュールの関数だけを呼び出す。
 * Demo 1 ではメモリ上のモックデータを操作するが、FastAPI 移行時は
 * 関数シグネチャを維持したまま中身を fetch に置き換える。
 *
 *   getInquiries        -> GET   /inquiries?q=&status=
 *   getInquiryById      -> GET   /inquiries/{id}
 *   createInquiry       -> POST  /inquiries
 *   updateInquiryStatus -> PATCH /inquiries/{id}/status
 */
import { MOCK_INQUIRIES } from "./mock-data";
import type {
  CreateInquiryInput,
  Inquiry,
  InquiryQuery,
  InquiryStatus,
} from "./types";

// サーバープロセスのメモリ上に保持する（再起動で初期状態に戻る）
const inquiries: Inquiry[] = MOCK_INQUIRIES.map((inquiry) => ({ ...inquiry }));
let nextId = inquiries.length + 1;

/** 呼び出し側の変更がストアに波及しないよう、常にコピーを返す */
const clone = (inquiry: Inquiry): Inquiry => ({ ...inquiry });

/** 問い合わせ一覧を作成日時の新しい順で返す。q はタイトル・本文の部分一致（大文字小文字を区別しない） */
export async function getInquiries(
  query: InquiryQuery = {},
): Promise<Inquiry[]> {
  const keyword = query.q?.trim().toLowerCase() ?? "";

  return inquiries
    .filter((inquiry) => !query.status || inquiry.status === query.status)
    .filter(
      (inquiry) =>
        !keyword ||
        inquiry.title.toLowerCase().includes(keyword) ||
        inquiry.description.toLowerCase().includes(keyword),
    )
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    .map(clone);
}

/** 該当なしの場合は null（API の 404 に相当） */
export async function getInquiryById(id: string): Promise<Inquiry | null> {
  const inquiry = inquiries.find((item) => item.id === id);
  return inquiry ? clone(inquiry) : null;
}

/** id・status・createdAt はサーバー側（API 移行後は FastAPI 側）で決定する */
export async function createInquiry(
  input: CreateInquiryInput,
): Promise<Inquiry> {
  const inquiry: Inquiry = {
    id: String(nextId++),
    title: input.title,
    description: input.description,
    category: input.category,
    status: "OPEN",
    createdAt: new Date().toISOString(),
  };
  inquiries.push(inquiry);
  return clone(inquiry);
}

/** 該当なしの場合は null（API の 404 に相当） */
export async function updateInquiryStatus(
  id: string,
  status: InquiryStatus,
): Promise<Inquiry | null> {
  const inquiry = inquiries.find((item) => item.id === id);
  if (!inquiry) {
    return null;
  }
  inquiry.status = status;
  return clone(inquiry);
}

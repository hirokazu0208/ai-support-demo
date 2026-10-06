export const INQUIRY_STATUSES = ["OPEN", "IN_PROGRESS", "CLOSED"] as const;
export type InquiryStatus = (typeof INQUIRY_STATUSES)[number];

export const INQUIRY_CATEGORIES = [
  "ACCOUNT",
  "NETWORK",
  "SOFTWARE",
  "OTHER",
] as const;
export type InquiryCategory = (typeof INQUIRY_CATEGORIES)[number];

export const INQUIRY_STATUS_LABELS: Record<InquiryStatus, string> = {
  OPEN: "未対応",
  IN_PROGRESS: "対応中",
  CLOSED: "完了",
};

export const INQUIRY_CATEGORY_LABELS: Record<InquiryCategory, string> = {
  ACCOUNT: "アカウント",
  NETWORK: "ネットワーク",
  SOFTWARE: "ソフトウェア",
  OTHER: "その他",
};

export type Inquiry = {
  id: string;
  title: string;
  description: string;
  category: InquiryCategory;
  status: InquiryStatus;
  /** ISO 8601 文字列（APIのJSONレスポンスと同じ形） */
  createdAt: string;
};

/** GET /inquiries のクエリパラメータに対応 */
export type InquiryQuery = {
  q?: string;
  status?: InquiryStatus;
};

/** POST /inquiries のリクエストボディに対応（id・status・createdAtはサーバー側で決定） */
export type CreateInquiryInput = {
  title: string;
  description: string;
  category: InquiryCategory;
};

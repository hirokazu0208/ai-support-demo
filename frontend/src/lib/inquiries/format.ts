const dateTimeFormatter = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/** ISO 8601 文字列を「2026/10/06 17:30」形式（日本時間）に整形する */
export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

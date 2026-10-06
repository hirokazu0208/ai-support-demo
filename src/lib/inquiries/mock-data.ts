import type { Inquiry } from "./types";

export const MOCK_INQUIRIES: Inquiry[] = [
  {
    id: "1",
    title: "パスワードを忘れてログインできない",
    description:
      "社内ポータルのパスワードを失念しました。リセット手順を教えてください。",
    category: "ACCOUNT",
    status: "OPEN",
    createdAt: "2026-09-28T00:15:00.000Z",
  },
  {
    id: "2",
    title: "会議室のWi-Fiに接続できない",
    description:
      "3階第2会議室で社内Wi-Fiに接続できません。他のフロアでは問題なく接続できます。",
    category: "NETWORK",
    status: "IN_PROGRESS",
    createdAt: "2026-09-29T01:40:00.000Z",
  },
  {
    id: "3",
    title: "Excelが起動直後に強制終了する",
    description:
      "昨日のWindows Update以降、Excelを起動すると数秒で終了してしまいます。",
    category: "SOFTWARE",
    status: "OPEN",
    createdAt: "2026-09-30T02:05:00.000Z",
  },
  {
    id: "4",
    title: "新入社員のアカウント発行依頼",
    description:
      "10月入社予定の2名について、メールアカウントと社内システムのアカウント発行をお願いします。",
    category: "ACCOUNT",
    status: "CLOSED",
    createdAt: "2026-09-24T05:30:00.000Z",
  },
  {
    id: "5",
    title: "VPN接続が頻繁に切断される",
    description:
      "在宅勤務中、VPNが30分ほどで切断されます。再接続すると一時的に復旧します。",
    category: "NETWORK",
    status: "OPEN",
    createdAt: "2026-10-01T23:50:00.000Z",
  },
  {
    id: "6",
    title: "画像編集ソフトのライセンス追加",
    description:
      "デザインチームで1名増員のため、画像編集ソフトのライセンスを1つ追加してください。",
    category: "SOFTWARE",
    status: "IN_PROGRESS",
    createdAt: "2026-10-02T04:20:00.000Z",
  },
  {
    id: "7",
    title: "複合機で両面印刷ができない",
    description:
      "2階の複合機で両面印刷を指定しても片面で出力されます。ドライバ設定を確認してほしいです。",
    category: "OTHER",
    status: "OPEN",
    createdAt: "2026-10-03T06:10:00.000Z",
  },
  {
    id: "8",
    title: "退職者アカウントの無効化",
    description:
      "9月末で退職した社員のアカウントを無効化してください。対象者は別途メールで送付済みです。",
    category: "ACCOUNT",
    status: "CLOSED",
    createdAt: "2026-09-30T08:45:00.000Z",
  },
];

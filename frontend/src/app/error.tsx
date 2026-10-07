"use client"; // エラーの境界は Client Component である必要がある

import Link from "next/link";
import { useEffect } from "react";

/**
 * API 停止・通信失敗・API の 5xx・不正な応答など、予期しないエラー時の画面。
 * 存在しない問い合わせ（repository が null を返す場合）は notFound() → not-found.tsx で扱う。
 *
 * error.message は表示しない（本番では Server Component のエラーは汎用メッセージに置き換わるが、
 * 開発時は元のメッセージが届くため）。digest はサーバーログと照合するための ID のみ表示する。
 */
export default function ErrorPage({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    // 開発者向け。原因の詳細は Next.js サーバーのログに digest 付きで出力される
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-start gap-4">
      <h1 className="text-2xl font-semibold">データを取得できませんでした</h1>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        問い合わせデータの取得中にエラーが発生しました。時間をおいて再度お試しください。
      </p>
      {error.digest && (
        <p className="text-xs text-zinc-500">エラー ID: {error.digest}</p>
      )}
      <div className="flex items-center gap-4">
        <button
          type="button"
          // データを再取得して再描画する（Next.js 16 では reset() ではなく retry() を使う）
          onClick={() => retry()}
          className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-80"
        >
          再試行
        </button>
        <Link
          href="/inquiries"
          className="text-sm text-zinc-600 underline hover:text-foreground dark:text-zinc-400"
        >
          ← 一覧へ戻る
        </Link>
      </div>
    </div>
  );
}

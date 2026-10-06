# AI Support Desk

社内ヘルプデスク担当者向けの問い合わせ管理 Web アプリです。
人間が要件定義・設計承認・レビュー・受入判断を行い、ChatGPT と Claude Code を工程ごとに使い分けた AI 支援開発で、段階的に開発しています。

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`frontend/`](frontend/) | Next.js 16（App Router）による画面。詳細は [frontend/README.md](frontend/README.md) |
| `backend/` | Python / FastAPI による REST API（Demo 2 で追加予定） |

## Demo の段階

| Demo | 内容 | 状態 |
|---|---|---|
| Demo 1 | Next.js の UI と、インメモリのモックデータによる問い合わせ管理 | 完了（タグ `demo-1`） |
| Demo 2 | FastAPI + SQLAlchemy + SQLite による REST API とデータ永続化 | 開発中 |

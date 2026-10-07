"""AI Agent が呼び出す業務 Tool。

Tool は既存の repository（業務ロジック）を呼ぶ薄い層で、検索・登録などの処理を重複実装しない。
各 Tool は名前・説明・引数モデルを持ち、LLM Agent（Demo 3 Step 5）の tool 定義にそのまま使える。
"""

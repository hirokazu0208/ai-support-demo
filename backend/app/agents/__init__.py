"""AI Agent。利用者のメッセージを受け取り、必要な Tool を呼び出して応答を組み立てる。

Agent の実装は Agent プロトコル（base.py）に従う。現在は RuleBasedAgent のみで、
LLM Agent（Demo 3 Step 5）は同じプロトコルで実装し、routers/agent.py の get_agent() で差し替える。
"""

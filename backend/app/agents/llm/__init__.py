"""LLM Agent（Demo 3 Step 5）。LLM が許可リストの Tool を選んで呼び出す Agent。

- client.py: LLM プロバイダに依存しない Protocol と型（OpenAI SDK は import しない）
- agent.py: LLMAgent（Tool Calling の制御・上限・AgentReply の生成）
- prompts.py: システム指示
プロバイダ SDK との変換（OpenAI Responses API 等）は別のアダプターが担当する。
"""

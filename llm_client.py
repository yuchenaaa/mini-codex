"""LLM 调用封装。用 openai 库,base_url/model/key 由调用方传入(provider 无关)。

chat():把 messages 发给模型,拿回一条 assistant 消息(可带 tools)。
summarize():独立一次调用,把历史压成摘要,供 History.compress() 注入。
"""

from openai import OpenAI


class LLMClient:
    def __init__(self, api_key, base_url, model):
        if not api_key:
            raise RuntimeError("API key 不能为空。")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def chat(self, messages, tools=None):
        """把整个 messages 列表发给模型,返回模型的 assistant 消息对象。
        tools:工具清单(OpenAI tools 格式)。传了模型才知道有哪些工具可调。"""
        kwargs = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message

    def summarize(self, text: str) -> str:
        """把一段 agent 工作记录压缩成要点。供 History.compress() 注入使用。
        独立的一次 LLM 调用,不带工具。"""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是对话摘要助手。把下面的 agent 工作记录压缩成简洁要点,"
                    "务必保留:做过哪些操作、读/改了哪些文件(含文件名)、关键结论。"
                    "不要编造,只总结已发生的内容。"
                ),
            },
            {"role": "user", "content": text},
        ]
        resp = self._client.chat.completions.create(
            model=self._model, messages=messages
        )
        return resp.choices[0].message.content or ""

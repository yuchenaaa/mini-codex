"""消息历史管理。

整个 agent 只有这一个地方持有 messages 列表 —— "单一收口"。
所有读写都过它,所以加 Context 压缩时,只动这个文件,主循环不用改。

压缩策略:总结式压缩 + 保留首尾(对标 Codex)。见 compress()。
"""

import json

import config


def _render(messages) -> str:
    """把一段消息拼成可读文本,喂给 summarizer 去总结。
    工具结果可能很长,截断到 500 字符,避免摘要输入本身又爆掉。"""
    lines = []
    for m in messages:
        role = m.get("role")
        if role == "user":
            lines.append(f"用户: {m.get('content', '')}")
        elif role == "assistant":
            for tc in m.get("tool_calls") or []:
                fn = tc["function"]
                lines.append(f"助手调用工具 {fn['name']}({fn['arguments']})")
            if m.get("content"):
                lines.append(f"助手: {m['content']}")
        elif role == "tool":
            lines.append(f"工具结果: {str(m.get('content', ''))[:500]}")
    return "\n".join(lines)


class History:
    def __init__(self, system_prompt: str):
        # 头:系统提示词,永远保留。压缩时也不动它。
        self._messages = [{"role": "system", "content": system_prompt}]

    def add_user(self, content: str):
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, message):
        # message 是模型返回的整条 assistant 消息(阶段 2 会带 tool_calls)。
        # 转成普通 dict 再存:这样下一轮重新发给模型时,tool_calls 能正确序列化。
        self._messages.append(message.model_dump(exclude_none=True))

    def add_tool_result(self, tool_call_id: str, content: str):
        # 阶段 2 用:把工具执行结果回灌给模型
        self._messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": content}
        )

    def get(self):
        """返回喂给模型的完整 messages 列表。"""
        return self._messages

    def save(self, path: str):
        """把当前完整对话写到磁盘,供下次续聊。存档失败不影响主流程。"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._messages, f, ensure_ascii=False, default=str)
        except Exception:
            pass

    def load(self, path: str) -> bool:
        """从磁盘读回上次对话,整体替换当前历史。成功返回 True。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                msgs = json.load(f)
        except Exception:
            return False
        if isinstance(msgs, list) and msgs:
            self._messages = msgs
            return True
        return False

    def _estimated_tokens(self) -> int:
        """估算整个历史的 token 数(零依赖近似,不追求和 GLM 分词器逐字一致)。
        规则:中日韩字符约 1 token/字;其余字符约 1 token / 4 字符。"""
        text = json.dumps(self._messages, ensure_ascii=False, default=str)
        cjk = other = 0
        for ch in text:
            # CJK 表意文字 + 中日韩标点/假名/谚文,按 1 字 ≈ 1 token 估
            if "一" <= ch <= "鿿" or "　" <= ch <= "ヿ" or "가" <= ch <= "힣":
                cjk += 1
            else:
                other += 1
        return cjk + other // 4

    def compress(self, summarizer) -> bool:
        """总结式压缩 + 保留首尾。触发并压缩了返回 True,否则 False。

        三个约束(SPEC.md §10):
          ① 头(system + 首条 user 任务)保留,尾(最近 KEEP_TAIL 条)保留,中段总结。
          ② 总结要调一次 LLM —— summarizer 当参数注入,History 不绑定具体模型。
          ③ 按"完整轮次"切:尾部起点若是孤立的 tool 结果,往前挪到拥有它的
             assistant,绝不拆散 tool_call 与 tool 结果的配对。
        """
        if self._estimated_tokens() <= config.COMPRESS_THRESHOLD_TOKENS:
            return False

        msgs = self._messages
        head_n = config.KEEP_HEAD
        # 太短就不值得压(头 + 尾 + 1 条摘要都装不下)
        if len(msgs) <= head_n + config.KEEP_TAIL + 1:
            return False

        # 约束③:确定尾部起点,并保证它不是孤立的 tool 结果
        start = len(msgs) - config.KEEP_TAIL
        while start > head_n and msgs[start].get("role") == "tool":
            start -= 1  # 往前挪,把发起这些 tool 调用的 assistant 一起纳入尾部

        head = msgs[:head_n]
        middle = msgs[head_n:start]
        tail = msgs[start:]
        if not middle:
            return False

        # 约束②:把中段交给 summarizer 总结(这一步真正调一次模型)
        summary = summarizer(_render(middle))
        # 摘要用 user 角色注入:OpenAI 兼容接口对 user 消息位置最宽容,最不容易报错
        summary_msg = {
            "role": "user",
            "content": f"[以下是早前对话的摘要,供你参考]\n{summary}",
        }
        self._messages = head + [summary_msg] + tail
        return True

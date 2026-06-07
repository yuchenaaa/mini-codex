"""Agent loop —— mini-codex 的核心。

一次用户输入,可能触发模型多轮工具调用。这里就是那个循环:
  把 messages + 工具发给模型
    -> 模型要调工具? 执行 -> 把结果塞回历史 -> 再问模型(循环)
    -> 模型给文字答案?  返回给用户,本轮结束
"""

import tools
from approval import ApprovalManager

# 安全上限:防止模型陷入死循环(对标失败模式里的 "loop")
MAX_STEPS = 15


class Agent:
    def __init__(self, client, history):
        self.client = client
        self.history = history
        self.approval = ApprovalManager()

    def run(self, user_input: str) -> str:
        """处理一次用户输入,返回最终的文字答案。"""
        self.history.add_user(user_input)

        for _ in range(MAX_STEPS):
            # 每轮调模型前,历史太长就先压缩(总结式压缩 + 保留首尾)
            if self.history.compress(self.client.summarize):
                print("  [上下文压缩] 历史过长,已把早前对话总结成摘要。")

            message = self.client.chat(self.history.get(), tools=tools.TOOLS_SCHEMA)
            self.history.add_assistant(message)

            # 模型没有要调工具 -> 这是最终答案,结束本轮
            if not message.tool_calls:
                return message.content or ""

            # 模型要调一个或多个工具 -> 先过审批,再执行,把结果塞回历史
            for call in message.tool_calls:
                name = call.function.name
                args = call.function.arguments

                approved, reason = self.approval.check(name, args)
                if not approved:
                    # 没批准:不执行,把拒绝原因回灌给模型,让它换条路
                    self.history.add_tool_result(call.id, f"[未执行] {reason}")
                    continue

                print(f"  [调用工具] {name}({args})")
                result = tools.execute_tool(name, args)
                self.history.add_tool_result(call.id, result)
            # for 跑完,回到 while 顶部,带着工具结果再问一次模型

        return "[已达到最大步数上限,提前停止。]"

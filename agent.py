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

    def run(self, user_input: str, plan_mode: bool = False) -> str:
        """处理一次用户输入,返回最终的文字答案。
        plan_mode=True 时只规划不执行:让模型输出分步计划,不给它任何工具。"""
        self.history.add_user(user_input)

        if plan_mode:
            return self._make_plan()

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

    def _make_plan(self) -> str:
        """规划模式:让模型只输出一份分步执行计划,不调用任何工具、不动手。
        关键:调 chat 时不传 tools —— 模型物理上就无法执行操作,只能输出文字计划。"""
        plan_messages = self.history.get() + [
            {
                "role": "user",
                "content": (
                    "现在是【规划模式】。你是产品方案设计者,不是写代码的。"
                    "请针对上面的需求,想清楚关键的【玩法/产品设计决策】,"
                    "而不是用什么文件或工具。请输出:\n"
                    "1) 核心设计要点:把这个东西需要拍板的关键选择列出来。"
                    "例如做贪吃蛇就该想:速度分几档、撞墙是直接失败还是从另一边穿过、"
                    "是否计分以及怎么计分、要不要多个关卡/难度、用什么控制方式等;\n"
                    "2) 对每个要拍板的点,给出你建议的默认值,并列出还有哪些可选项,"
                    "方便用户据此调整。\n"
                    "禁止:不要写实现步骤,不要提到读写哪个文件或调用什么工具,不要写代码。"
                    "此刻只产出设计方案,等用户确认或调整。"
                ),
            }
        ]
        message = self.client.chat(plan_messages)  # 不传 tools
        self.history.add_assistant(message)
        return message.content or ""

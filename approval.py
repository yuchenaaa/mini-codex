"""审批闸门 —— 安全的核心。

对标 Codex 的 ApprovalDecision:危险操作执行前,代码强制停下来问人。
跟模型态度无关 —— 模型问不问、怎么措辞,都绕不过这一关。

三层结构(见 SPEC.md §8):
  第 1 层 黑名单:极危险命令直接拒,不问(tools.is_dangerous_command)
  第 2 层 审批  :write_file / run_shell 执行前问人 y/n/a  ← 本文件
  第 3 层 执行  :tools.execute_tool
"""

import json

import tools

# 哪些工具需要审批。read_file 是只读的,安全,不需要。
NEEDS_APPROVAL = {"write_file", "run_shell"}


def _describe(name: str, args: dict) -> str:
    """把"模型要干什么"翻译成人能一眼看懂的一句话。"""
    if name == "write_file":
        content = args.get("content", "")
        return f"写入文件 {args.get('path')}({len(content)} 字符)"
    if name == "run_shell":
        return f"执行命令: {args.get('command')}"
    return f"{name}({args})"


class ApprovalManager:
    def __init__(self):
        self._always = set()  # 本 session 内已选"全部同意"的工具名

    def check(self, name: str, arguments_json: str) -> tuple:
        """返回 (是否放行, 给模型的说明)。
        放行 -> (True, None);拒绝 -> (False, 回灌给模型的原因)。"""
        if name not in NEEDS_APPROVAL:
            return True, None

        try:
            args = json.loads(arguments_json)
        except json.JSONDecodeError:
            args = {}

        # 第 1 层:run_shell 命中黑名单 -> 直接拒,连问都不问
        if name == "run_shell":
            bad = tools.is_dangerous_command(args.get("command", ""))
            if bad:
                cmd = args.get("command", "")
                print(f"  [自动拒绝] 命令含危险模式 '{bad}',已拦截:{cmd}")
                return False, f"被安全策略拒绝:命令含危险模式 '{bad}'。"

        # 本 session 已对此类操作"全部同意"
        if name in self._always:
            return True, None

        # 第 2 层:停下来问人
        print(f"\n  ⚠️  mini-codex 想要:{_describe(name, args)}")
        ans = input("     批准? [y]同意一次  [n]拒绝  [a]本类全部同意 > ").strip().lower()

        if ans == "a":
            self._always.add(name)
            return True, None
        if ans == "y":
            return True, None
        # 其它一律当拒绝。把拒绝回灌给模型,让它知道并换路。
        return False, "用户拒绝了这次操作。"

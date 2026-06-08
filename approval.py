"""审批闸门 —— 安全的核心。

对标 Codex 的 ApprovalDecision:危险操作执行前,代码强制停下来问人。
跟模型态度无关 —— 模型问不问、怎么措辞,都绕不过这一关。

三层结构(见 SPEC.md §8):
  第 1 层 黑名单:极危险命令直接拒,不问(tools.is_dangerous_command)
  第 2 层 审批  :write_file / run_shell 执行前问人 y/n/a  ← 本文件
  第 3 层 执行  :tools.execute_tool
"""

import difflib
import json
import os

import tools

# 哪些工具需要审批。read_file 是只读的,安全,不需要。
NEEDS_APPROVAL = {"write_file", "run_shell"}


_DIFF_MAX_LINES = 40  # diff 超过这么多行就截断,避免审批时刷屏


def _write_preview(path: str, content: str) -> str:
    """写文件前的"改动预览":把 现有内容 vs 将写入内容 的差异打出来,
    让审批从"盲批"(只知道路径和字数)变"明批"(看得到具体要改什么)。"""
    exists = os.path.exists(path)
    old = ""
    if exists:
        try:
            with open(path, "r", encoding="utf-8") as f:
                old = f.read()
        except Exception:
            old = ""
    head = f"修改文件 {path}" if exists else f"新建文件 {path}"
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(),
            content.splitlines(),
            fromfile="现在",
            tofile="将变成",
            lineterm="",
        )
    )
    if not diff_lines:
        return f"{head}(内容无变化)"
    shown = diff_lines[:_DIFF_MAX_LINES]
    body = "\n".join("       " + ln for ln in shown)
    if len(diff_lines) > _DIFF_MAX_LINES:
        body += f"\n       ... (省略 {len(diff_lines) - _DIFF_MAX_LINES} 行)"
    return f"{head},改动预览:\n{body}"


def _describe(name: str, args: dict) -> str:
    """把"模型要干什么"翻译成人能一眼看懂的描述。"""
    if name == "write_file":
        return _write_preview(args.get("path", ""), args.get("content", ""))
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

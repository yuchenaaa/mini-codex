"""工具系统:3 个工具的"声明"和"执行"。

两部分:
  1. TOOLS_SCHEMA —— 用 OpenAI tools 格式描述工具,发给模型看,模型据此决定调谁。
  2. execute_tool() —— 模型说"我要调 X",我们在这里真正执行 X。

这就是 Codex 工具系统的最小版:声明 / 路由 / 执行。
"""

import json
import os
import subprocess

import config


# ===== 第 1 部分:工具声明(给模型看的"说明书")=====
# 描述写得好不好,直接决定模型会不会、何时调这个工具 —— 这是 AI PM 的核心交付物。
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取一个文本文件的全部内容。当你需要了解某个文件里写了什么时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径,可以是相对或绝对路径"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出一个文件夹下的文件和子文件夹。当你不确定目录里有什么、需要先摸清结构时调用(比如刚进一个项目,先看看有哪些文件)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件夹路径,不填则列当前目录"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把内容写入一个文件(覆盖原内容)。用于新建文件或修改文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "要写入的文件路径"},
                    "content": {"type": "string", "description": "要写入的完整内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "在 PowerShell 中执行一条命令并返回输出。用于跑测试、跑脚本、查看目录等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"}
                },
                "required": ["command"],
            },
        },
    },
]


# ===== 第 2 部分:工具执行 =====

def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[读取失败] {e}"


def _list_dir(path: str = ".") -> str:
    try:
        entries = sorted(os.listdir(path))
    except Exception as e:
        return f"[列目录失败] {e}"
    if not entries:
        return "[空目录]"
    lines = []
    for name in entries:
        full = os.path.join(path, name)
        suffix = "/" if os.path.isdir(full) else ""
        lines.append(f"{name}{suffix}")
    return "\n".join(lines)


def _write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[写入成功] {path}({len(content)} 字符)"
    except Exception as e:
        return f"[写入失败] {e}"


def is_dangerous_command(command: str):
    """第 1 层防护:命中黑名单返回命中的那个模式,否则 None。
    approval 层和 _run_shell 都用它(纵深防御:两道关都查)。"""
    low = command.lower()
    for bad in config.DANGEROUS_PATTERNS:
        if bad in low:
            return bad
    return None


def _run_shell(command: str) -> str:
    # 纵深防御:即使调用方没走审批,这里也兜一道黑名单
    bad = is_dangerous_command(command)
    if bad:
        return f"[已拒绝] 命令包含危险模式 '{bad}',出于安全未执行。"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = result.stdout + result.stderr
        return out.strip() or "[命令执行完毕,无输出]"
    except subprocess.TimeoutExpired:
        return "[执行超时] 命令超过 30 秒未结束。"
    except Exception as e:
        return f"[执行失败] {e}"


# 路由表:工具名 -> 真正干活的函数
_DISPATCH = {
    "read_file": lambda a: _read_file(a["path"]),
    "list_dir": lambda a: _list_dir(a.get("path", ".")),
    "write_file": lambda a: _write_file(a["path"], a["content"]),
    "run_shell": lambda a: _run_shell(a["command"]),
}


def execute_tool(name: str, arguments_json: str) -> str:
    """模型说要调 name(参数是 JSON 字符串),我们在这里执行,返回结果文本。"""
    if name not in _DISPATCH:
        return f"[未知工具] {name}"
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError as e:
        return f"[参数解析失败] {e}"
    return _DISPATCH[name](args)

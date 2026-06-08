"""mini-codex 交互入口。

启动后用向导依次问:① 选 provider → ② 填 API key → ③ 填模型名 → ④ 选文件夹,
然后进入 REPL:你输入一句,agent 可能自主调用工具多轮,直到给出答案。
输入 exit / quit 退出。
"""

import os
import sys

import config
from agent import Agent
from history import History
from llm_client import LLMClient

SYSTEM_PROMPT = (
    "你是 mini-codex,一个跑在命令行里的编程助手。"
    "你可以使用工具读文件、写文件、跑命令来完成任务。"
    "需要了解或操作文件时,主动调用工具,不要凭空猜测文件内容。"
    "回答简洁、直接。"
)

# Windows 经典控制台默认不认 ANSI 转义;这一句空 system 调用会触发它开启,
# 之后下面的蓝色高亮才生效(PowerShell / Windows Terminal 本就支持)。
if os.name == "nt":
    os.system("")

_BLUE = "\033[94m"   # 亮蓝色(bright blue),深色终端上清晰可读
_RESET = "\033[0m"


def _cmd(text: str) -> str:
    """把斜杠命令染成蓝色,让用户一眼看出这是个"功能",不是普通文字。"""
    return f"{_BLUE}{text}{_RESET}"


# 斜杠命令清单:(命令, 说明)。新增命令时只改这里,/ 和 /help 自动跟着更新。
COMMANDS = [
    ("/plan <需求>", "进入规划模式,先出计划;之后可继续说话反复改计划"),
    ("/go", "对计划满意了,按计划开始执行(退出规划模式)"),
    ("/help", "显示这份命令清单"),
    ("exit", "退出"),
]


def _print_commands():
    print("\n  可用命令:")
    for cmd, desc in COMMANDS:
        print(f"    {_cmd(cmd)}  —  {desc}")
    print()


# 所有斜杠命令的前缀,用于把用户刚输入的命令名染蓝
_SLASH_PREFIXES = ("/plan", "/help", "/go", "/run", "/do")


def _recolor_input_line(prompt: str, text: str):
    """普通 input() 不能"边打边变色",所以这里在用户回车后,
    把刚才那一行重绘一次:命令名(如 /plan)染成蓝色。
    注意:只能处理单个可视行,输入很长自动换行时会失效。"""
    low = text.lower()
    for p in _SLASH_PREFIXES:
        if low.startswith(p):
            text = _cmd(text[: len(p)]) + text[len(p):]
            break
    else:
        return  # 不是命令,不用重绘
    # 光标上移到输入行 -> 回到行首 -> 清整行 -> 重绘
    sys.stdout.write(f"\033[A\r\033[2K{prompt}{text}\n")
    sys.stdout.flush()


def _plan_reminder():
    """每次出完计划后固定提醒:现在还没动手,以及怎么退出规划模式。"""
    print(
        f"  ↑ 以上只是计划,还没动手。继续说话可以改计划;"
        f"满意了请输入 {_cmd('/go')} 才会开始执行。\n"
    )


def _select_provider():
    """① 让用户用数字选 provider,返回选中的预设字典。"""
    print("请选择你的 LLM 服务商:")
    for i, p in enumerate(config.PROVIDERS, start=1):
        print(f"  {i}. {p['name']}")
    while True:
        choice = input("输入序号 > ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(config.PROVIDERS):
            return config.PROVIDERS[int(choice) - 1]
        print("  输入无效,请输入列表里的序号。")


def _setup():
    """启动向导:依次问 provider / key / 模型 / 文件夹。返回 (api_key, base_url, model)。"""
    provider = _select_provider()

    api_key = input(f"\n请输入你的 {provider['name']} API key > ").strip()

    model = input(
        f"请输入模型名(直接回车用默认 {provider['default_model']}) > "
    ).strip()
    if not model:
        model = provider["default_model"]

    workdir = input("请输入工作文件夹路径(直接回车用当前目录) > ").strip()
    if workdir:
        try:
            os.chdir(workdir)
        except (FileNotFoundError, NotADirectoryError):
            print(f"  目录无效:{workdir},改用当前目录。")

    return api_key, provider["base_url"], model


def main():
    print("=== mini-codex 启动向导 ===\n")
    api_key, base_url, model = _setup()

    print(f"\nmini-codex 就绪 | 模型:{model} | 工作目录:{os.getcwd()}")
    print(f"输入 {_cmd('/')} 或 {_cmd('/help')} 查看所有命令;{_cmd('exit')} 退出。\n")

    client = LLMClient(api_key, base_url, model)
    history = History(SYSTEM_PROMPT)
    agent = Agent(client, history)
    plan_mode = False  # 规划模式开关:开着时所有输入都只改计划、不动手

    # 续聊:工作目录下若有上次会话存档,问要不要接着聊
    session_path = os.path.abspath(config.SESSION_FILE)
    if os.path.exists(session_path):
        ans = input("发现上次会话存档,继续上次聊天吗? [y/n] > ").strip().lower()
        if ans == "y" and history.load(session_path):
            print("  已载入上次会话,可以接着聊。\n")
        else:
            print("  以全新会话开始(存档会被这次对话覆盖)。\n")

    while True:
        try:
            # 规划模式下提示符变成蓝色 (plan),让你时刻知道现在不会动手
            prompt = f"你 {_cmd('(plan)')} > " if plan_mode else "你 > "
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break

        # 用户回车后,把刚输入的命令名(如 /plan)重绘成蓝色
        _recolor_input_line(prompt, user_input)

        if user_input.lower() in ("exit", "quit"):
            print("再见。")
            break
        if not user_input:
            continue
        # 输入 / 或 /help:打印命令清单(命令名蓝色高亮)
        if user_input in ("/", "?") or user_input.lower() == "/help":
            _print_commands()
            continue

        # /plan <需求>:进入规划模式(粘性)。进来后你可以反复说话改计划,
        # 期间一律只规划、不执行;直到你 /go 确认满意,才退出并真正动手。
        if user_input.lower().startswith("/plan"):
            plan_mode = True
            req = user_input[len("/plan"):].strip()
            if not req:
                print("  [已进入规划模式] 说出需求,我先出计划;不满意就继续说来改,"
                      f"满意了输入 {_cmd('/go')} 开始执行。\n")
                continue
            answer = agent.run(req, plan_mode=True)
            print(f"\nmini-codex > {answer}\n")
            history.save(session_path)
            _plan_reminder()
            continue

        # /go [补充]:确认计划、立刻开始执行。退出规划模式,带工具真正动手。
        # 关键:用"首个词"判断,所以 /go 后面跟的文字不会让它落空 ——
        # 那段文字会被当作"补充要求"一并执行,而不是又去改计划。
        first = user_input.split(maxsplit=1)
        if first[0].lower() in ("/go", "/run", "/do"):
            if not plan_mode:
                print("  当前不在规划模式,直接说需求即可,无需 /go。\n")
                continue
            plan_mode = False
            extra = first[1].strip() if len(first) > 1 else ""
            instruction = "我已确认上面的计划,现在开始执行。"
            if extra:
                instruction += f"另外补充一点要求:{extra}"
            # 不传 plan_mode(默认 False)-> 带工具,真正动手
            answer = agent.run(instruction)
            print(f"\nmini-codex > {answer}\n")
            history.save(session_path)
            continue

        # 普通输入:规划模式里就是"继续调整计划";否则正常执行。
        answer = agent.run(user_input, plan_mode=plan_mode)
        print(f"\nmini-codex > {answer}\n")
        history.save(session_path)
        if plan_mode:  # 还在规划模式 -> 这次是改计划,再提醒一次怎么退出
            _plan_reminder()


if __name__ == "__main__":
    main()

"""mini-codex 交互入口。

启动后用向导依次问:① 选 provider → ② 填 API key → ③ 填模型名 → ④ 选文件夹,
然后进入 REPL:你输入一句,agent 可能自主调用工具多轮,直到给出答案。
输入 exit / quit 退出。
"""

import os

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
    print("输入 exit 退出。\n")

    client = LLMClient(api_key, base_url, model)
    history = History(SYSTEM_PROMPT)
    agent = Agent(client, history)

    while True:
        try:
            user_input = input("你 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break

        if user_input.lower() in ("exit", "quit"):
            print("再见。")
            break
        if not user_input:
            continue

        answer = agent.run(user_input)
        print(f"\nmini-codex > {answer}\n")


if __name__ == "__main__":
    main()

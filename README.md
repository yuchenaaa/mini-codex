# mini-codex

一个跑在命令行里的**通用 coding agent**,从零实现了 AI agent 的三个核心机制:
**agent loop(自主多轮工具调用)+ 工具系统 + 安全审批**。

它是 [OpenAI Codex](https://github.com/openai/codex) 的最小可运行复刻——主体 ~600 行,
用来彻底讲清楚"一个 agent 在底层到底是怎么运转的"。

> 设计取舍、踩过的坑、与真 Codex 的差距,都写在 [DESIGN.md](DESIGN.md)。

---

## 它能做什么

在命令行里用自然语言指挥它,它会**自己决定调用工具**完成任务:

| 场景 | 你说 | 它做 |
|---|---|---|
| 摸清目录 | "这文件夹是干嘛的?" | 先 `list_dir` 看有哪些文件,再 `read_file` 读 README 回答 |
| 读 + 答 | "SPEC.md 讲的是什么?" | 自己 `read_file` 读完再回答 |
| 写文件 | "写个脚本算斐波那契,存成 fib.py" | `write_file` 落盘(执行前给 **diff 预览** + 问你) |
| 改 + 验证 | "运行 fib.py 看看对不对" | `run_shell` 跑命令(执行前问你) |

四个工具:`list_dir`(只读)/ `read_file`(只读)/ `write_file`(写前审批)/ `run_shell`(跑前审批 + 黑名单)。

**规划模式**:输入 `/plan <需求>` 让它先出一份"产品设计方案"(只规划、不动手);你可以接着说话反复改方案,
满意了再输入 `/go` 才开始执行。输入 `/` 或 `/help` 查看所有命令(命令名蓝色高亮)。

**续聊**:每轮对话自动存档到工作目录,下次启动可选择载入、接着上次聊(只保留最近一次)。

对话变长时会**自动做总结式 context 压缩**:按 token 预算估算,历史超过(模型窗口 − 回复余量)时,
把中段对话交给模型总结成摘要、保留首尾,腾出上下文空间(对标 Codex 的 compact;实现与三个约束见 [DESIGN.md](DESIGN.md))。

---

## 快速开始

需要 Python 3.x 和一个 LLM API key(支持任何 OpenAI 兼容厂商:智谱 GLM / DeepSeek / 通义千问 / Kimi / 腾讯混元 / MiniMax 等)。

**方式一:直接运行**

```powershell
pip install -r requirements.txt
python main.py
```

**方式二:装成命令(推荐,像 codex 一样在任意目录敲 `mini_codex` 启动)**

```powershell
pip install .
mini_codex
```

> 若提示找不到 `mini_codex`:是你的 Python Scripts 目录(形如 `...\PythonXXX\Scripts`)不在系统 PATH 上。
> 把它加入 PATH 后开新窗口即可——这一步配一次,以后所有 pip 安装的命令都能直接敲。

启动后按提示依次:**① 数字选服务商 → ② 填 API key → ③ 填模型名(可回车用默认) → ④ 选工作文件夹**,
然后就能在该目录里用自然语言对话、干活。若该目录有上次会话存档,还会问你**要不要接着上次聊**。

可选服务商预设写在 [config.py](config.py) 的 `PROVIDERS` 里,可自行增改(各家 base_url / 模型名以官方文档为准)。

---

## 项目结构

```
main.py          交互入口:启动向导 + REPL + 斜杠命令(/plan、/go、/help)+ 续聊存档
agent.py         agent loop —— 核心:多轮工具调用直到任务完成;含规划模式(只出方案不动手)
tools.py         工具系统:4 个工具的声明 + 路由 + 执行
approval.py      安全审批闸门:执行危险操作前停下来问人;写文件前给 diff 预览
history.py       消息历史(单一收口)+ token 预算压缩(保留首尾、不破坏 tool 配对)+ 会话存档/载入
llm_client.py    LLM 调用封装(openai 库,base_url/model/key 由调用方传入,provider 无关)
config.py        provider 预设 / token 预算参数 / 续聊文件名 / 危险命令黑名单
pyproject.toml   打包配置:pip install 后注册 mini_codex 命令
requirements.txt 依赖清单
SPEC.md          需求与边界(动手前先定的)
DESIGN.md        架构、安全分层、设计取舍、踩坑复盘
```

---

## 安全

三层防御(对标 Codex 的前两层):

1. **黑名单** —— `rm -rf` / `Remove-Item` 等极危险命令直接拒,不问
2. **审批闸门** —— `write_file` / `run_shell` 执行前**代码强制**停下来问人(y/n/a);写文件前先展示 **diff 预览**,让你"明批"而非"盲批"
3. **执行**

⚠️ **明确的边界**:本项目**不做 OS 沙箱**,也没有 Codex 的命令级 exec policy 和 Guardian。
为什么、差距在哪、怎么补,见 [DESIGN.md 的"安全的诚实边界"](DESIGN.md)。

---

## 不在范围内(刻意砍掉的)

OS 沙箱 · 多 agent · MCP · 流式输出。

这些不是没想到,是 MVP 刻意划掉的边界——理由都写在 SPEC.md 和 DESIGN.md 里。

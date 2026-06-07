# mini-codex MVP Spec (v0.1)

> 一个通用命令行 coding agent —— Codex 主循环 + 工具系统 + 安全审批的最小可运行复刻。
> 学习/简历作品。作者:智能投研 PM,转 AI Agent PM 方向。

---

## 1. 项目名字
`mini-codex`

## 2. 核心定位
一个**通用命令行 coding agent**:能读文件、改文件、跑命令,在一个 agent loop 里自主完成小型编程任务。
本质是把 Codex 的三个核心机制做最小复刻:**agent loop + 工具系统 + 安全审批**。

## 3. 核心场景

| # | 场景 | 一句话演示 |
|---|---|---|
| S1 | **读 + 答** | "这个项目是干嘛的?" → agent 自主 `read_file` 看代码后回答 |
| S2 | **写新文件** | "写一个 Python 脚本算斐波那契" → agent `write_file` 落盘 |
| S3 | **改 + 验证** | "这个函数有 bug,修一下" → agent 读 → 改 → `run_shell` 跑测试验证 |

S3 是最能体现"agent 自主闭环"的场景,面试演示重点。

## 4. MUST vs NICE TO HAVE

| MUST(v1 必须有) | NICE TO HAVE(以后再说) |
|---|---|
| Agent loop(多轮工具调用直到任务完成) | 多 agent / sub-agent |
| 3 个工具:`read_file` / `write_file` / `run_shell` | MCP 接入 |
| 危险命令拦截 + 写文件/跑命令前审批 | 流式输出(streaming) |
| 命令行交互界面 | **Context 压缩(预留接口,见 §10)** |
| 消息历史管理(`History` 模块) | OS 级沙箱 |

## 5. 模型
- 厂商:智谱 GLM(走 OpenAI 兼容接口)
- 模型:`glm-4.7`(报错则回退 `glm-4.6` / `glm-4-plus`)
- SDK:Python `openai` 库,改 `base_url`
- 端点:`https://open.bigmodel.cn/api/paas/v4`
- v1 **不开流式**(GLM 流式 + tool call 偶有边角问题,且 streaming 属 NICE TO HAVE)

## 6. 运行环境
- Windows 11 + Python 3.x
- `run_shell` 工具在 PowerShell 中执行命令

## 7. 工具清单(v1 只做 3 个)

| 工具 | 输入 | 作用 | 安全等级 |
|---|---|---|---|
| `read_file` | 路径 | 读文件内容 | 安全,免审批 |
| `write_file` | 路径 + 内容 | 写/覆盖文件 | **写前审批** |
| `run_shell` | 命令字符串 | 跑命令 | **跑前审批 + 黑名单** |

工具以 OpenAI `tools` 格式声明(function calling),让 GLM 自主决定调用。

## 8. 安全约束(对标 Codex 4 层防御的最小版)

- **审批闸门**:`write_file` 和 `run_shell` 执行前,打印要做什么,用户敲 y/n 决定
- **危险命令黑名单**:`rm -rf` / `del /f` / `format` / `shutdown` / `rmdir /s` 等直接拒绝
- **审批 3 选项**(对标 Codex ApprovalDecision 的简化版):
  - `y` = 同意这一次
  - `n` = 拒绝(把拒绝理由回灌给模型)
  - `a` = 本 session 内此类操作全部同意
- v1 **不做 OS 沙箱**(Codex 投入最大的部分,太重),靠"审批 + 黑名单"兜底
  - 面试时诚实讲:做了 4 层里的前 2 层,理解了为什么 Codex 还需要后 2 层(审批会疲劳、黑名单会漏)

## 9. 成功标准

| 场景 | 通过标准 |
|---|---|
| S1 读+答 | agent 自主调 `read_file` 后给出正确回答,不瞎编 |
| S2 写文件 | 生成的脚本能跑出正确结果 |
| S3 改+验证 | agent 自主完成 读 → 改 → 跑测试 → 看到通过 全闭环 |
| 安全 | `rm -rf` 被黑名单拦下;`write_file` / `run_shell` 执行前一定先问 |

## 10. Context 压缩 —— v1 不实现,但预埋接口

v1 不做压缩,但消息历史封装成独立的 `History` 模块,为未来"总结式压缩 + 保留首尾"留口子。
有效预留需满足三个条件:

| 条件 | v1 状态 |
|---|---|
| ① 单一收口:所有 messages 读写都过 `History` | ✅ 实现 |
| ② `compress()` 能注入一个 summarizer(总结需额外一次 LLM 调用) | ✅ 签名预留,空实现 |
| ③ 按"完整轮次"切,不破坏 `tool_call` 与 `tool` 结果的配对 | ✅ 留注释说明,v1 不切 |

承诺:未来加压缩,**只动 `History` 模块,agent loop 与工具代码一行不改**。

## 11. 技术栈与文件结构

- Python 3.x + `openai` 库(指向 GLM)
- 目标代码量:300–600 行

```
mini-codex/
├── main.py          # 交互入口(命令行 REPL)
├── agent.py         # agent loop(多轮工具调用调度)
├── tools.py         # 3 个工具的定义 + 执行
├── history.py       # 消息历史管理 + 压缩预留接口
├── llm_client.py    # GLM 调用封装
├── config.py        # API key、模型名、黑名单
├── SPEC.md          # 本文档
└── DESIGN.md        # 架构说明(面试材料,后补)
```

## 12. 范围外(明确不做)
- 不放 GitHub(作者自行 git 提交)
- 不做 OS 沙箱 / 多 agent / MCP / 流式 / 真压缩实现

---

## 开发阶段

| 阶段 | 目标 | 验证 |
|---|---|---|
| 阶段 1 | 骨架可跑(纯对话) | 能跟 GLM 来回对话 |
| 阶段 2 | 加工具系统 + agent loop | 能自主调 read/write/shell 完成任务 |
| 阶段 3 | 加安全(审批 + 黑名单)+ UX | 危险命令被拦,写/跑前审批 |
| 阶段 4 | 文档(README + DESIGN.md) | 面试可讲 |

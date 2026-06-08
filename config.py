"""集中放配置:API key、模型、端点、危险命令黑名单。
key 从环境变量读,不写死在代码里(避免泄露)。"""

import os

# ---- 模型与端点 ----
# GLM 走 OpenAI 兼容接口,只需改 base_url
BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
MODEL = "glm-4.7"  # 若控制台报模型名不存在,改成 glm-4.6 或 glm-4-plus

# key 从环境变量 GLM_API_KEY 读取(老的非交互方式,保留兼容;交互式启动不依赖它)
API_KEY = os.environ.get("GLM_API_KEY", "")

# ---- provider 预设(交互式启动时供用户用数字选)----
# 都走 OpenAI 兼容接口,区别只是 base_url 和模型名。用户选完 provider 再填 key、可改模型名。
# ⚠️ base_url / 默认模型名以各厂商官方文档为准,可能变动:
#    - DeepSeek / 通义千问(DashScope) / Kimi(Moonshot):较有把握
#    - 腾讯混元 / MiniMax:地址与模型名变动较多,使用前请按官网复核
PROVIDERS = [
    {"name": "DeepSeek",     "base_url": "https://api.deepseek.com",                          "default_model": "deepseek-chat"},
    {"name": "腾讯混元",      "base_url": "https://api.hunyuan.cloud.tencent.com/v1",          "default_model": "hunyuan-turbo"},
    {"name": "通义千问 Qwen",  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-plus"},
    {"name": "Kimi (Moonshot)", "base_url": "https://api.moonshot.cn/v1",                      "default_model": "moonshot-v1-8k"},
    {"name": "MiniMax",      "base_url": "https://api.minimax.chat/v1",                       "default_model": "abab6.5s-chat"},
    {"name": "智谱 GLM",      "base_url": "https://open.bigmodel.cn/api/paas/v4",             "default_model": "glm-4.7"},
]

# ---- Context 压缩参数(token 级预算)----
# 思路:模型的上下文窗口是按 token 算的。我们不等"撑爆"才动,而是给回复留好余量,
# 历史的估算 token 一旦超过 (窗口 - 余量),就触发总结式压缩。
#
# ⚠️ MODEL_CONTEXT_TOKENS 是模型窗口大小,以官方文档为准。GLM-4.7 的确切值请到
#    智谱控制台核实;拿不准就往小了填,宁可早压缩也别撑爆报错。
MODEL_CONTEXT_TOKENS = 128_000     # 模型上下文窗口(token),按你用的模型改
RESPONSE_RESERVE_TOKENS = 8_000    # 给模型本轮回复 + 工具调用预留的 token 余量
# 历史估算 token 超过这个阈值就压缩
COMPRESS_THRESHOLD_TOKENS = MODEL_CONTEXT_TOKENS - RESPONSE_RESERVE_TOKENS

# ---- 会话续聊 ----
# 每轮对话后把完整历史存到工作目录下这个文件;下次启动可选择载入接着聊。
# 只保留最近一次(同名文件覆盖写)。
SESSION_FILE = ".mini_codex_session.json"

KEEP_HEAD = 2   # 头:保留 system + 第一条 user 任务
KEEP_TAIL = 6   # 尾:保留最近多少条消息

# ---- 危险命令黑名单(第 1 层:直接拒,不问)----
# 诚实地说:字符串黑名单永远列不全(换个写法就能绕),它只是"绝不放过的极危险项"。
# 真正的安全靠第 2 层审批闸门(approval.py)——任何写/跑操作都要人点头。
DANGEROUS_PATTERNS = [
    "rm -rf",
    "del /f",
    "rmdir /s",
    "rd /s",
    "remove-item",   # Windows 上 rm 的真名,补上洞 2 发现的那个变体
    "format",
    "shutdown",
    "mkfs",
]

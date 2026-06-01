# rx-plugin 安装与避坑指南

> 这是 [Song-ic/rx-plugin](https://github.com/Song-ic/rx-plugin) 的修复版 fork（`DQT-bit/rx-plugin`），
> 修好了原版在 **reasonix 0.53.x + Windows** 上无法落地代码的 3 个问题（见文末「踩过的坑」）。
> 本文档自包含：换电脑、给朋友、或让 AI agent 读，照着走即可一步到位。

---

## 这是什么

把 **Claude 当大脑、Reasonix（DeepSeek 驱动的廉价 agent CLI）当手** 串成一条流水线的 Claude Code 插件：

```
你提需求 → Claude 出规格(spec) → rx-go 经 ACP 派发给 Reasonix 落地代码 → Claude 验收
```

Claude 负责思考/出规格/验收，真正改代码交给 Reasonix（比 Claude 直接写便宜 ~30-90× token）。

---

## 前置依赖

| 依赖 | 用途 | 检查命令 |
|------|------|----------|
| **Node.js ≥ 22** | reasonix CLI + ACP client | `node --version` |
| **Python 3**（`python` 或 `python3` 任一可运行）| rx-go 写 task state | `python --version` |
| **Reasonix CLI** | 执行端 | `reasonix --version` |
| **DeepSeek API key** | Reasonix 调模型 | platform.deepseek.com 申请 |
| **Claude Code** | 插件宿主 | — |

> 🇨🇳 国内装 reasonix 走淘宝镜像：`npm i -g reasonix --registry https://registry.npmmirror.com`

---

## 安装（6 步）

### 1. 装 Reasonix CLI 并配置
```bash
npm i -g reasonix          # 国内加 --registry https://registry.npmmirror.com
reasonix setup             # 按向导输入 DeepSeek API key；MCP 可全跳过
reasonix doctor            # 应全绿（api key / config / api reach 都 ok）
```

> ⚠️ **关键配置**：`reasonix setup` 默认 `editMode=review`（改动要人工 /apply 确认，
> 非交互派发时文件不会自动落盘）。**改成 `auto`**：编辑 `~/.reasonix/config.json`，
> 把 `"editMode": "review"` 改为 `"editMode": "auto"`（自动落盘 + 保留 undo）。

### 2. 装插件（修复版）
**Claude Code CLI** 里：
```
/plugin marketplace add DQT-bit/rx-plugin
/plugin install rx@rx-plugin
```
重启 Claude Code。

> 如果你的环境 `/plugin` 命令不可用（如桌面客户端），见文末「手动安装」。

### 3. 验证整条链路
在任意有 `.git` 的项目目录里：
```bash
rx-doctor
```
期望：`reasonix doctor` 段 **10 ok · 0 warn · 0 fail**，末尾 `✅ 链路健康`。

### 4. 跑第一个任务
```
/rx:go 给 utils.py 加一个 slugify(text) 函数，带 unittest，全部测试要通过
```
Claude 会出规格 → 经 ACP 派发 Reasonix 落地 → 验收。

---

## 工作原理（一句话版）

`rx-go` **不用** `reasonix run`（那个模式只把工具调用当文本输出、不执行），
而是经 `bin/rx-acp-dispatch.mjs` 走 **`reasonix acp`**（Agent Client Protocol，
stdio NDJSON JSON-RPC）。ACP 才会真正驱动 `write_file` / `run_command` 把改动落到磁盘。

---

## 踩过的坑（原版在 reasonix 0.53.x + Windows 上的 3 个 bug，本 fork 已修）

> 如果你用的是**原版** Song-ic/rx-plugin 且遇到「dispatch 跑完没动静 / 文件没生成 / exit 49」，
> 就是下面这些。本 fork 全部修好了。

### 坑 1：`reasonix run --preset` —— 选项不存在
原版 rx-go 调 `reasonix run ... --preset auto`，但 `reasonix run` **没有 `--preset`**，
每次 `error: unknown option '--preset'` exit 1。
**修复**：preset 映射成 reasonix 真有的 `--model`（flash/pro/auto）。

### 坑 2：`reasonix run` 只「说」不「做」（核心）
`reasonix run` 模式把工具调用当**文本**流式打印（如 `<bash command="..."/>`），但**不执行**，
文件永远不落盘。整条流程静默产出空结果，最难发现。
**修复**：改走 `reasonix acp`（见「工作原理」），ACP 真正执行工具。

### 坑 3：`python3` 是 Windows Store 占位符 → exit 49
很多 Windows 装机上 `python3` 是 Microsoft Store 的 alias stub：
`command -v python3` **找得到**（指向 `WindowsApps\python3`），但一运行就 **exit 49**。
原版 rx-go 用 `python3` 写 state.json，这个 49 会泄漏成 rx-go 的退出码，
**盖住 dispatch 的真实结果**。
**修复**：探测时**实跑 `--version`**（不只 `command -v`），取第一个真正能运行的解释器。
> 💡 通用教训：在 Windows 上判断解释器可用性，`command -v` 不够，Store stub 存在但跑不了，必须实跑验证。

---

## 手动安装（`/plugin` 不可用时）

把仓库 clone 到两处 + 注册两个 json：
```bash
# 1. clone 到 marketplaces 和 cache
git clone https://github.com/DQT-bit/rx-plugin.git \
  ~/.claude/plugins/marketplaces/rx-plugin
git clone https://github.com/DQT-bit/rx-plugin.git \
  ~/.claude/plugins/cache/rx-plugin/rx/0.1.5
```
然后在 `~/.claude/plugins/known_marketplaces.json` 加 `rx-plugin` 条目、
在 `installed_plugins.json` 的 `plugins` 里加 `"rx@rx-plugin"`（schema 参照同文件里已有条目）。
重启 Claude Code。

---

## 验证清单（确认真的能用）

- [ ] `reasonix doctor` 全绿
- [ ] `~/.reasonix/config.json` 的 `editMode` = `auto`
- [ ] `rx-doctor` 末尾 `✅ 链路健康`
- [ ] `/rx:go <小任务>` 真的生成了文件、测试能跑过、rx-go exit 0

全部打勾 = 一步到位，没踩坑。

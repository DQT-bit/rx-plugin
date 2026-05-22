# rx — Reasonix Bridge

> Claude Code plugin：把 **"Claude 当大脑、Reasonix 当手"** 的协作工作流打包成一条可复用链路。

Claude 负责思考、出规格、验收；Reasonix（DeepSeek 驱动的廉价 agentic 代码执行 CLI）负责真正落地代码改动。实测同样的开发任务，比 Claude 直接写便宜 **30-40 倍**。

## 链路全景

```
你（提需求）
   ↓
Claude Code  ── 大脑：理解需求 → 出规格 .reasonix-tasks/*.md
   ↓  /rx:go 或 rx-go dispatch
reasonix CLI ── 手：调 DeepSeek API → 实际改项目代码
   ↓
Claude Code  ── 大脑：4 步验证 → 通过 / 失败回路（≤3 次）
```

一句话：**Claude 出规格 + 验收，reasonix 干体力活，DeepSeek 提供廉价算力。**

## 完整链路需要什么

| 依赖 | 用途 | 必需 |
|---|---|---|
| [Claude Code](https://claude.com/claude-code) | 大脑 + 本 plugin 的宿主 | ✅ |
| Node.js | 装 reasonix CLI（走 npm） | ✅ |
| Python 3 | 跑 gatekeeper hook + 写 task state | ✅ |
| bash | rx-go / rx-doctor / rx-clean 脚本（macOS/Linux 自带，Windows 用 WSL） | ✅ |
| **DeepSeek API key** | reasonix 调用的算力 —— **要你自己去申请**，见下方第 2 步 | ✅ |

## 安装 —— 完整 6 步

### 1. 装 Reasonix CLI

```bash
npm i -g reasonix
```

### 2. 申请 DeepSeek API key　←　这一步是你要自己准备的

1. 打开 <https://platform.deepseek.com/> 注册 / 登录
2. 左侧 **API keys** → **Create new API key**
3. 复制生成的 key（形如 `sk-xxxxxxxxxxxxxxxx`）—— **只显示一次，存好**

> DeepSeek 按 token 计费，非常便宜。先充值一点点（够用很久），再继续。

### 3. 把 key 配进 reasonix

```bash
reasonix setup
```

交互式向导，把上一步的 DeepSeek API key 粘进去即可。
**key 存在 reasonix 自己的配置里，不在本 plugin 仓库内** —— 所以本仓库公开也不会泄露你的 key。

### 4. 验证 reasonix

```bash
reasonix doctor
```

应全绿。报错通常是 key 没配对 / 网络问题，按提示修。

### 5. 装本 plugin

```bash
claude plugin marketplace add Song-ic/rx-plugin
claude plugin install rx@rx
```

然后**重启 Claude Code**。

### 6. 验证整条链路

重启后在任意项目里跑：

```bash
rx-doctor
```

它检查 reasonix CLI / 脚本 / gatekeeper / 用量 —— 全绿即整条链路打通。

## 用法

| 入口 | 说明 |
|---|---|
| `/rx:go <任务描述>` | 完整协作流程：Claude 出规格 → `rx-go` dispatch → 4 步验证 |
| `rx-go <规格文件> [预算] [preset]` | 直接调度一个规格（脚本，装 plugin 后自动进 PATH） |
| `rx-clean` | 清理 `.reasonix-tasks/` `.reasonix-logs/` 旧文件（默认 7 天前） |
| `rx-doctor` | 链路体检 |

**skill**（Claude 按场景自动触发）：

- `tdd-loop` —— Reasonix-first TDD 闭环（Claude 写测试 → reasonix 实现 + 自验 + 自修）
- `audit-swarm` —— 并行多角色代码审计（安全 / 性能 / 测试 / UX / 质量）

典型流程：你说"加个 XX 功能" → Claude 读代码、写规格 → `rx-go` 派给 reasonix → reasonix 改代码 → Claude 编译/测试验收 → 通过或进失败回路。完整机制见 [`rules/reasonix-workflow.md`](rules/reasonix-workflow.md)。

## gatekeeper 闸门

plugin 自带一个 PreToolUse hook（`hooks/reasonix-gatekeeper.py`）：拦截 Claude 直接用 Edit/Write/MultiEdit/NotebookEdit 改业务代码超过 3 行的尝试，强制走 reasonix 流，保证"大脑不动手"。

> ⚠️ plugin 被禁用时 hook 随之失效，闸门关闭。依赖这条铁律的话，确保 plugin 处于启用状态（`rx-doctor` 会检查 hook 是否在岗）。

## 成本

reasonix 走 DeepSeek、按 token 计费，非常便宜。单个规格、单个 phase 的预算参考见 [`rules/reasonix-workflow.md`](rules/reasonix-workflow.md) 第七节。`rx-doctor` 末尾附 `reasonix stats` 用量摘要，也可直接 `reasonix stats` 看完整面板。

## 项目约定

用本 plugin 的项目，把这两个目录加进 `.gitignore`：

```
.reasonix-tasks/
.reasonix-logs/
```

## 组件一览

| 组件 | 作用 |
|---|---|
| `commands/go.md` | `/rx:go` 命令 |
| `bin/rx-go` | dispatch 脚本 |
| `bin/rx-doctor` · `bin/rx-clean` | 体检 / 清理 |
| `hooks/` | gatekeeper hook |
| `skills/` | tdd-loop / audit-swarm |
| `rules/reasonix-workflow.md` | 完整工作流手册 |
| `templates/spec-template.md` | 规格起步模板 |

## 许可

MIT —— 见 [LICENSE](LICENSE)。

---
name: audit-swarm
description: |
  Parallel multi-role code audit — dispatches 5 specialist agents simultaneously (security / UX / performance / test coverage / code quality) to audit a codebase, consolidates findings into a ranked table, and presents top items for user approval before any fixes.

  TRIGGER when user says: "audit swarm", "audit this codebase", "全面 audit", "parallel review", "5-role review", "接手项目盘一下", "ship 前最后 audit", "季度盘点".

  DO NOT TRIGGER for: routine bug fix, small PR review (use /review instead), ongoing feature work. This is a high-cost operation (150-400k tokens) reserved for inflection points.
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - Agent
---

# Audit Swarm — 并行多角色代码审计

## 何时用(贵但值)

| 场景 | 用 | 不用 |
|---|---|---|
| 接手新项目第一次盘 | ✅ | |
| 大版本 ship 前 | ✅ | |
| 季度 / 半年盘点 | ✅ | |
| 接手别人的烂代码 | ✅ | |
| 日常 PR review | | ❌(用 /review) |
| 单 bug 调试 | | ❌(用 /investigate) |
| 1-3 个文件改动 | | ❌(过度) |

**成本警告**:单次跑 ~150-400k token(5 个 sub-agent × 30-80k 各),约 $1.5-4 USD。**用之前问用户确认**,不要默默 spawn。

## 工作流(4 阶段)

### 阶段 1 — 范围确定(Claude 直做,~5 min)

用户说"audit swarm" 时,先**确认范围**:

> Audit swarm 准备启动(预算 ~$2-3,约 200-400k token)。先确认:
> 1. 审什么? 整个 repo / 某个模块 / 某次 PR diff
> 2. 项目根目录绝对路径
> 3. 这次重点关心的是? (默认 5 个维度全审,可以挑 2-3 个加权)
> 4. 严不严? 默认 "blocking only"(critical+high)报告,要全的话说 "exhaustive"

跑一些 fast scout(`tokei` / `cloc` 算代码量、`tree -L 2` 看结构),给用户一份预览:
```
代码量: Java 12k 行 / Vue 8k 行
模块数: 8 个 module
预估跑完时间: 3-5 分钟
预估总成本: $2.4
要继续吗?
```

等用户 "继续" 再阶段 2。

### 阶段 2 — 并行 dispatch 5 个 agent(Agent 工具,parallel call)

一条消息内 spawn 5 个 Agent,subagent_type 选 `general-purpose`,**严格限定** scope 和输出格式:

```
Agent 1: 安全审计
  prompt: 审 <path>,扫 OWASP top 10 + secrets in code + auth/authz 漏洞 + SQL 注入 + XSS。
         返回 JSON 数组 [{severity: critical|high|medium|low, file: path:line, issue: ..., suggested_fix: ...}]。
         < 400 words 总输出,只 cite 真实文件路径,不写代码块。

Agent 2: 性能审计
  prompt: 审 <path>,扫 N+1 query / 死循环 / 不必要的同步阻塞 / 缓存缺失 / 大对象传值。
         同上 JSON 格式。

Agent 3: 测试覆盖
  prompt: 审 <path>,识别没测试的关键路径(business logic without test)、
         flaky test patterns、test 跟实现强耦合处。同上 JSON 格式。

Agent 4: UX/前端(如果有 frontend)
  prompt: 审 <vue/react path>,扫 a11y 缺失 / loading state 缺失 / error state 缺失 /
         无障碍 / 移动适配。同上 JSON 格式。

Agent 5: 代码质量
  prompt: 审 <path>,扫 dead code / 重复代码 / circular dep / 太长的方法 / 不一致的命名。
         同上 JSON 格式。
```

**parallel call** = 一条消息里 5 个 Agent tool use block。

### 阶段 3 — 合并 + 去重 + 排序(Claude 直做)

5 个 agent 返回后:
1. 合并所有 JSON
2. 去重(同一文件:行多个 agent 提到的相似 issue)
3. 按 severity 排序:critical → high → medium → low
4. 做成表格,**只显示 top 20**(其余 "want full report? say so"):

```markdown
| # | Sev | File:Line | Issue | Suggested Fix | Source |
|---|---|---|---|---|---|
| 1 | 🔴 critical | UserController.java:42 | SQL 注入(参数没 escape) | 用 PreparedStatement | security |
| 2 | 🔴 critical | LoginService.java:88 | JWT secret hardcoded | 移到 application-prod.yml | security |
| 3 | 🟠 high | OrderService.java:156 | N+1 query 拉 1000 行 | join 或 IN clause | perf |
| ... |
```

总结一句:`5 个 agent 审计完毕。发现 critical 2 / high 7 / medium 11 / low 3。要看完整报告说 'show all',要进 fix 流程说 'fix top N'。`

### 阶段 4 — fix 编排(可选,用户指令触发)

用户说 "fix top 5" / "fix all critical":

按 Reasonix 工作流,**为每个 finding 写一个修复规格** → rx-go dispatch → Claude 验证。

**重要**:**不**用 git worktree fan-out(原始报告建议的)—— 那是 over-engineering。串行 fix 已经够快,简单可靠。

每个 fix:
```
1. Read 文件 确认 finding 描述属实(agent 可能误判)
2. 写 .reasonix-tasks/<date>-audit-fix-N.md
3. rx-go <规格> 0.05
4. Claude 4 步验证(compile/启动/curl/SHOW TABLES)
5. 失败回路 ≤ 3
6. 等用户 commit 指令(不自动)
```

跑完 N 个 fix,出汇总:
```
✅ 修了 5 个 finding(2 critical + 3 high)
- Reasonix 总成本: $0.18
- 改动文件: 8 个
- 测试: 全 152/152 通过
- 待 commit
```

## 何时跳过 audit swarm 单跑某个 agent

如果你只关心一个维度,**直接 spawn 一个 Agent** 就行,不必凑 5 个:
- "只审安全" → 1 个 security agent
- "只看测试覆盖" → 1 个 coverage agent

这能省 80% 成本。

## 成本预算参考

| 范围 | 5-agent 总 token | 估算 USD |
|---|---|---|
| 小模块(~3k 行) | 80-150k | $0.5-1.0 |
| 中等项目(~15k 行) | 200-350k | $1.5-2.5 |
| 大 monorepo(~50k 行) | 400-600k | $3-5 |

修复阶段额外 $0.05-0.15 per finding(reasonix 价格)。

## 跟其他命令的关系

- `/review` 主用 gstack,审单个 PR diff —— 用那个,别用 audit swarm
- `/cso` 已经做"全栈安全审计" —— 跟 audit swarm 的 Agent 1 重叠;如果重点是安全,优先 /cso
- `/gsd-code-review` 是 phase 级跨 commits 审 —— 比 audit swarm 范围窄,跑得快
- audit swarm 是**整个 repo 全方位扫**的最重武器,慎用

## 注意事项

- 不要在小项目(< 1000 行)上用 — 杀鸡用牛刀
- 不要每周都跑 — 大部分时间日常 /review 就够
- agent 报告要复审(他们偶尔会幻觉,特别是 "suggested fix" 部分)— **不要盲信**,fix 前 Claude 必须 Read 该文件确认 issue 真实

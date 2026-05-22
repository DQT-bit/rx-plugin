# Reasonix 工作流手册

> `rx` plugin 的详细机制手册。`/rx:go` 命令与 skill 引用本文。

## 一、角色定义

- **Claude = 大脑** — 思考 / 判断 / 出规格 / 验收。不直接改项目代码。
- **Reasonix = 手** — 执行所有项目代码改动。

闭环：Claude 思考 → 出规格 → Reasonix 执行 → Claude 验收 →（有问题）→ 出修复规格 → ...

## 二、何时走 reasonix

```
要改项目内文件吗？
  否 → Claude 直做（规格 / 文档 / 验收 / 诊断）
  是 → ≤3 行 + 单文件 + 不新增符号？
        是 → Claude 直做 + 明说"绕过 reasonix（原因：xxx）"
        否 → reasonix 流（出规格 + rx-go dispatch + 4 步验证）
```

gatekeeper hook 会硬拦截违规改动 —— 但它是兜底，不是借口。Claude 应主动判断、主动走 reasonix。沉默偏离例外路径 = 严重违规。

## 三、规格 7 段

规格文件放 `.reasonix-tasks/<yyyymmdd>-<slug>.md`，骨架见 `templates/spec-template.md`：

1. **项目根目录** — `PROJECT_ROOT=<绝对路径>`，必写。
2. **目标** — 一句话。
3. **项目上下文** — 技术栈、包名/签名/框架惯例（reasonix 最容易在这翻车）。
4. **参考实现** — 贴绝对路径让 reasonix Read。⚠️ reasonix 文件沙箱限定在项目根内，项目外的参考要贴全文或先 `cp` 进项目。
5. **涉及文件** — 绝对路径，分新建 / 修改。
6. **改动指令** — 复杂算法贴完整伪代码，修改型贴 before/after。
7. **完成判据** — 机器可验证（编译退出码、curl 返回）。禁主观判据。
+ **不得改动** / **翻车点**。

**规格质量 = Claude 核心交付物。** Reasonix 失败 ≥ 2 次基本都是规格不够好 —— 先查规格再 retry。

## 四、任务切分

每个 reasonix 规格 ≤ 200 行新代码 / ≤ 5 文件。按业务边界切：数据层 / 算法层 / 接口层 / 前端层各一个。依赖单向，每个 task 能独立编译通过。

## 五、4 步验证（每次 dispatch 后 Claude 必做）

1. **改动范围** — 看实际生成文件（路径、数量对不对，多出来的要质疑）。
2. **静态** — 编译 / lint（mvn compile、pnpm tsc、python ast.parse）。
3. **运行时** — 启动 / docker rebuild（如适用）。
4. **端到端** — curl / SHOW TABLES（如适用）。

任一失败 → 失败回路。

> reasonix 的 filesystem MCP 改文件后会重置执行权限 —— 改过的脚本记得重新 `chmod +x`。

## 六、失败回路（≤ 3 次硬上限）

- **第 1 次** — 读 stdout / 编译错，写修复规格（仅改的文件 + 指令 + 判据）重 dispatch。
- **第 2 次** — 重审原规格：上下文够不够？伪代码够不够细？参考实现贴了没？
- **第 3 次** — 停下来找用户。不要无限重试。

## 七、成本预算

| 任务 | 代码量 | 推荐预算 |
|---|---|---|
| 纯数据层（SQL + 实体 + Mapper） | ~150 行 | $0.10 |
| 核心算法 Service | ~200 行 | $0.15 |
| Controller + DTO | ~120 行 | $0.10 |
| 前端页 | ~250 行 | $0.20 |

单 phase（4-6 task）总成本通常 < $0.10。`rx-go` 不传预算时按规格行数自动估算；规格里写 `<!-- rx-budget: 0.12 -->` 可显式声明。

## 八、plugin 组件

| 组件 | 作用 |
|---|---|
| `/rx:go` | 触发完整 reasonix 协作流程 |
| `rx-go <规格> [预算] [preset]` | 调度脚本：预读规格 + 调 `reasonix run` + 写 task state |
| `rx-clean` | 清理 `.reasonix-tasks/` `.reasonix-logs/` 旧文件（默认 7 天前） |
| `rx-doctor` | 链路体检：reasonix CLI / 脚本 / gatekeeper / task state / 用量 |
| `reasonix-gatekeeper.py` | PreToolUse hook，拦截 Claude 越界改业务代码（Edit/Write/MultiEdit/NotebookEdit） |
| skill `tdd-loop` | Reasonix-first TDD 闭环 |
| skill `audit-swarm` | 并行多角色代码审计 |

task 状态记在 `.reasonix-tasks/state.json`（`rx-go` 写、`rx-doctor` 读）—— session 中断后 `rx-doctor` 能看到哪些 task dispatch 过、退出码是否正常。

## 九、删除操作的分工

reasonix 的文件工具集**包含** `delete_file` / `delete_directory` —— 它能删文件、删目录。但删除不可逆，按风险分工：

| 删除场景 | 谁做 |
|---|---|
| 规格明确、单个、安全（删掉某个确定的旧文件） | 写进 reasonix 规格，让它用 `delete_file` 删 |
| 删一批 / 删目录 / 路径拿不准 / 破坏性大 | Claude 把关 —— 先 `ls` 列清单、走确认闸门，不拆进规格 |

reasonix 是"照规格执行"、不会质疑路径对错；破坏性删除的把关由 Claude 做（先列清单、不可逆操作等用户确认）。

## 十、常见翻车点

- **MyBatis 关键字**：避免 `value` / `key` / `order` 作字段名 → 用 `prize_value` / `sort_order`。
- **事务回滚**：必须 `@Transactional(rollbackFor = Exception.class)`。
- **库存原子扣**：`setSql("stock = stock - 1")`，不在 Java 算。
- **Java 版本**：规格里写明（reasonix 易误用高版本语法到低版本项目）。
- **Vue 3**：用 `<script setup>`，不要 v-if + v-for 同元素。
- **reasonix 沙箱**：只能读写项目根内文件；改文件后会丢执行权限。

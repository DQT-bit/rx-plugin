---
description: 触发 Reasonix 协作流程 — Claude 出规格 + rx-go dispatch + 4 步验证
---

按 Reasonix 协作模式执行当前任务。

**铁律**：Claude = 大脑（思考、出规格、验收），Reasonix = 手（改项目代码）。Claude 不直接 Edit/Write 项目业务代码 —— 那是 reasonix 的工作。本 plugin 的 gatekeeper hook 会硬拦截超出例外阈值的违规改动。

**接收的任务描述**：$ARGUMENTS

**步骤（Claude 全程负责，不动项目代码）**：

1. **理解 + 调研**
   - 从上方任务描述 + 当前对话历史还原意图
   - Read 相关源码 / 参考实现（必须读关键文件，不凭印象）
   - 估算改动范围（几个文件 / 几行）

2. **写规格** → `.reasonix-tasks/<yyyymmdd>-<slug>.md`
   - 7 段格式：PROJECT_ROOT / 上下文 / 参考实现 / 涉及文件 / 改动指令（必含伪代码或精确 before-after）/ 完成判据（机器可验证）/ 不得改动
   - 脚手架见本 plugin 的 `templates/spec-template.md`
   - 翻车点段也写

3. **dispatch** → `rx-go .reasonix-tasks/<file>.md [预算USD] [preset]`
   - 预算可省略 —— rx-go 自动估算（规格头 `rx-budget:` 声明 / 缺省按行数估）
   - preset 可选 `auto`（默认）/ `flash`（更省）/ `pro`（更强）
   - 详细成本参考见本 plugin 的 `rules/reasonix-workflow.md` 第七节

4. **4 步验证**
   - 改动范围确认（看实际生成文件路径）
   - 编译 + 测试：Java 用 `mvn test`（不能只 `mvn compile`——不编 src/test、漏测试 desync），前端 `pnpm build` / `tsc`，Python `ast.parse` 或 pytest
   - 运行时（启动 / docker rebuild）— 如适用
   - 端到端（curl / SHOW TABLES）— 如适用

5. **失败回路 ≤ 3 次**
   - 第 1 次失败：看 stdout / 编译错，写"修复规格"重 dispatch
   - 第 2 次：重审原规格（上下文够不够 / 伪代码够不够细）
   - 第 3 次：**停下来找用户**，不要无限重试

**约束**：
- ❌ 不要 Edit/Write 项目代码（那是 reasonix 的工作）
- ❌ 不要自动 commit（commit 等用户明示）
- ✅ 唯一例外：≤3 行 + 单文件 + 不新增符号，且必须明说"绕过 reasonix（原因：xxx）"

完成后输出**简短总结**：改了哪几个文件 + 关键改动 1-2 句 + 用户感知到的变化。**不要**贴 reasonix 内部指标（cache hit / cost 等）。

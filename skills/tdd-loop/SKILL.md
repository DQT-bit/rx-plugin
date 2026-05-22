---
name: tdd-loop
description: |
  Reasonix-first TDD loop. Claude writes acceptance tests, then dispatches ONE fat reasonix spec with completion criteria "all tests pass" — reasonix implements + runs `mvn test` internally + self-fixes once. Claude only verifies at the end; only steps in to orchestrate round-by-round if reasonix can't close it in 2 attempts.

  PROACTIVELY TRIGGER when user asks for feature implementation that meets ALL these:
  (1) describes a feature/接口/算法 with clear contract (REST endpoint, public method, computable rule)
  (2) estimated > 30 lines OR > 2 files
  (3) project has working test runner (mvn test / pytest / vitest)
  → before starting, ASK one line: "估 ~N 行/M 文件,走 TDD loop 吗?(说 '不用' 跳过)"

  EXPLICIT TRIGGER: "tdd this", "tdd loop", "TDD 跑一下", "TDD this feature", "自动跑测试改到绿".

  DO NOT TRIGGER for: bug fix < 10 lines, UI/视觉 work, config-only changes, ambiguous spec (clarify first).
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
---

# TDD Loop — Reasonix-first 自动 TDD 闭环

## 核心架构(B+ 链路)

```
1. Claude 写 acceptance test(直接,不走 reasonix)
   ↓ 测试代码是"spec 的具象化",Claude 必须先看到测试确认捕捉到需求
   ↓ 贴给用户 review → 等 "approve"
2. Claude 写 ONE fat reasonix 规格
   ↓ 含:实施指令 + 参考实现 + 完成判据 = "mvn test 全过 + exit 0"
   ↓ 预算 $0.15(比普通规格高,因为含自验证)
3. rx-go dispatch
   ↓ Reasonix 自己: implement → 跑 mvn test → 失败的话同 dispatch 内自修一次 → 返回
4. Claude 复验(1 次)
   ↓ cd <root> && mvn test —— 看 exit code
   ↓ 全过 → 结束,等用户 commit
   ↓ 失败 → 进入 fallback
5. Fallback(失败回路)
   ↓ 第 1 次失败: refine spec(贴 mvn 输出 + 加翻车点)→ 再 dispatch
   ↓ 第 2 次失败: 切换到 round-by-round Claude orchestration(原 A 架构)
   ↓ 第 3 次失败: STOP — 找用户
```

**典型成本**:中等 feature 一次成功 ≈ $0.20;1 次 fallback ≈ $0.35;最坏(全降级)≈ $0.60。
**对比纯 Claude 编排**:同样工作量 $0.50,B+ 链路省 2-3 倍。

## 触发判定(scope-gated proactive)

### 自动触发条件(必须全满足)

| 条件 | 判断方法 |
|---|---|
| 有清晰契约 | 用户描述里有 endpoint URL / 方法签名 / 算法规则 / 数据 schema |
| 估改动 > 30 行 OR > 2 文件 | Grep 找现有类似 feature,看类似改动多大 |
| 有 working test runner | 跑 `ls pom.xml package.json pytest.ini` 看项目类型 |
| 非 bug fix(已知 root cause 的修复) | 用户没说"修 bug"/"为啥 500" |
| 非 UI 调整 | 改动不主要在 .vue / .css / 视觉 |

### 触发动作

满足时,Claude **不直接动手**,先一句话问:

> 估 ~80 行 / 3 文件,有清晰契约。走 TDD loop?(说 "不用" 跳过直接走 reasonix)

用户说 "走" → 进入阶段 1。
用户说 "不用" → 按 reasonix-workflow.md 普通流程走(直接出 implement 规格,不写 test 先)。
用户不说话 → 默认走 TDD(假设你回了 enter)。

### 显式触发

用户说 "tdd this XX" / "tdd loop" / "TDD 跑一下" → 跳过 scope 判定,直接进阶段 1。

### 不触发场景

- 用户说 "改 import 路径" / "改一行错" / "bump 版本"(< 10 行)
- 用户说 "调一下按钮颜色" / "改下页面布局"(UI/视觉)
- 用户说 "为啥这接口 500" / "查这个 bug"(根因不明,走 /investigate)
- 用户没说"实现 / 加 / 做 / 实施" 等 implementation 动词

## 阶段 1 — 写 acceptance test(Claude 直做)

**为啥 Claude 直写,不走 reasonix**:测试代码是 spec 的具象化。你要先看到测试本身确认它能正确捕捉需求,才能授权后续 implementation。这是"思考产物"边界内。

要求:
- 写 **acceptance test**(端到端,最贴近业务的),不是单元测试堆
- 覆盖:正常流(2-3 个)+ 关键 edge case(1-2 个)+ 错误处理(1-2 个)
- 命名清晰:`should_return_400_when_quantity_negative`
- 一次 3-8 个测试,超 10 个说明 spec 太大,**先拆 phase 不是先写测试**

写完贴出代码 + 每个测试一句话描述什么场景。**等用户 approve** 才进入阶段 2。

## 阶段 2 — Fat spec dispatch(Claude 写规格 → reasonix 全包)

### Fat spec 模板

```markdown
# TDD-Rx-N <feature 名>

## 项目根目录
PROJECT_ROOT=/绝对路径

## 目标
实现 <feature 一句话>。**完成判据 = 现有 acceptance test 全部通过 + 全项目 mvn test exit 0**。

## acceptance test 文件(已写好)
- `/绝对路径/src/test/java/.../FeatureXxxTest.java`

## 项目上下文
[同 reasonix-workflow.md 标准上下文段]

## 参考实现
[贴 1-3 个类似 feature 的绝对路径]

## 改动指令(详细伪代码)
[贴每个新建/修改文件的具体内容,Service 算法贴完整伪代码]

## 不得改动
[列具体文件路径]

## **完成判据(critical — 你必须自己验证再返回)**

1. `cd $PROJECT_ROOT && mvn -q compile` exit 0
2. `cd $PROJECT_ROOT && mvn -q test -Dtest=FeatureXxxTest` exit 0(本 feature 测试全过)
3. `cd $PROJECT_ROOT && mvn -q test` exit 0(全项目回归,所有测试全过)

判据 2 或 3 失败的话,**在同一次 dispatch 内**:
- 读测试输出找出失败原因
- 修改代码(implementation,不要改测试)
- 重跑 mvn test
- 通过后才返回"已完成"

最多自修 1 轮。1 轮还过不了就在响应里贴出失败的测试名 + mvn 输出,让 Claude 接手。
```

### Dispatch

```bash
rx-go .reasonix-tasks/<date>-tdd-<slug>.md 0.15
```

预算 $0.15(比普通 $0.05-0.10 高,因为 reasonix 要跑测试 + 可能自修)。

## 阶段 3 — Claude 复验(1 次,极简)

reasonix 返回后:

```bash
cd $PROJECT_ROOT && mvn -q test 2>&1 | tail -30
echo "exit: $?"
```

- exit 0 + "BUILD SUCCESS" → 进入阶段 4
- exit != 0 → 进入 fallback(阶段 5)

**不要再多做什么**(原 SKILL.md 里的 4 步验证简化掉)。Reasonix 已经在 dispatch 内自验过了,我们就是兜底 sanity check。

如果有时间和怀疑,可以扫一眼 git diff 看 reasonix 写的代码是否合理。但默认不做。

## 阶段 4 — 报告 + 等用户 commit

报告格式:

```markdown
✅ TDD loop 完成
- 测试: 8/8 本 feature 通过 + 152/152 全项目回归
- Reasonix 调用: 1 次(单次成功)
- 总成本: $0.14
- 改动文件:
  - 新建: 3 个(列文件)
  - 修改: 1 个(列文件)
- 待 commit
```

**绝不自动 commit** —— 等用户说 "commit" 指令。

## 阶段 5 — Fallback(失败回路)

### 第 1 次 mvn test 失败

不立刻升级到 round-by-round。先 **refine spec**:

```markdown
# TDD-Rx-N-fix-1 <feature 名>(fix 第 1 轮)

## 上次失败原因
[贴 mvn 输出关键行 + 失败的 test 名]

## 翻车分析
[你判断是 missing import / 算法错 / 边界没处理 / 还是别的]

## 修复指令
[针对失败原因写具体改动]

## 完成判据
同上(全测试必须过)
```

dispatch 一次,预算 $0.05。

### 第 2 次 mvn test 失败

升级到 **round-by-round Claude orchestration**(原 A 架构):
- Claude 读每个失败的 test 的 mvn 输出
- 拆成多个小修复 spec(每个 spec 修一个 test)
- 串行 dispatch + 跑 mvn test 复验

### 第 3 次仍失败

**STOP** — 出报告找用户:

```markdown
⚠️ TDD loop 卡住
- 失败的 test: <列表>
- 试过的修复策略:
  1. <第 1 次>
  2. <第 2 次>
- 我的判断:可能是 [spec 有歧义 / 边界条件没说清 / 项目里有 bug]
- 建议:[让用户决定怎么走]
```

## 跟 reasonix-workflow.md 的关系

- 通用 reasonix 工作流:本 plugin 的 `rules/reasonix-workflow.md`(规格 7 段模板、失败回路、成本预算)
- TDD loop **是其特化场景**:测试通过是机器可验证的 boolean 信号,适合让 reasonix 自验证 + 自修一次
- 普通 reasonix dispatch 没这个属性(代码正确性靠 Claude 看),所以普通工作 Claude 主导验证;TDD 推到 reasonix 内

## 常见翻车点

| 问题 | 处理 |
|---|---|
| Reasonix "声称已通过测试" 但实际 Claude 跑 mvn test 失败 | 不信 reasonix 自报,**永远以 Claude 复验为准** |
| Acceptance test 写得太多(20+ 个) | 拆 phase,这个 spec 不该一次做完 |
| Reasonix 改了测试让它过(作弊) | 在 spec "不得改动" 里**明确禁止改动 test 文件** |
| mvn test 跑超时 | 加 `-DforkCount=1 -DreuseForks=true` 或检查死循环 |
| 前置依赖缺失(DB 没跑 / Redis 没启) | 测试前 Claude 跑 docker ps 确认,缺的先启动 |

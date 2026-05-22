#!/usr/bin/env python3
"""Reasonix Gatekeeper - PreToolUse hook on Edit/Write/MultiEdit/NotebookEdit

按 Reasonix 协作模式铁律,拦截 Claude 直改业务代码的尝试。
触发条件:
  - tool ∈ {Edit, Write, MultiEdit, NotebookEdit}
  - file_path 是业务代码 / 元工程文件
  - 改动行数 > 3(超出例外阈值)

例外白名单(直接放行):
  - ~/.claude/** (Claude 自身大脑)
  - .reasonix-tasks/** / .reasonix-logs/** / .planning/** (规划产物)
  - *.md (项目文档)

业务代码黑名单(检查行数):
  - .py / .swift / .java / .kt / .ts / .tsx / .js / .jsx / .vue / .go / .rs / .sql
  - pom.xml / package.json / project.yml / Dockerfile / tsconfig.json / vite.config.*

Stdin: JSON {tool_name, tool_input, ...}
Exit 0 = allow / Exit 2 = block (stderr → Claude)
"""

import json
import os
import sys
import datetime
from pathlib import Path

ALLOWLIST_PATH_SUBSTR = [
    "/.claude/",
    ".reasonix-tasks/",
    ".reasonix-logs/",
    ".planning/",
    "/tmp/",
]

ALLOWLIST_FILENAMES = {
    "PROJECT.md", "PLAN.md", "ROADMAP.md", "README.md",
    "CHANGELOG.md", "ARCHITECTURE.md", "CLAUDE.md",
}

DOC_EXTENSIONS = {".md", ".rst", ".txt"}

BUSINESS_EXTENSIONS = {
    ".py", ".swift",
    ".java", ".kt", ".scala",
    ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte",
    ".go", ".rs",
    ".php", ".rb",
    ".sql",
    ".c", ".cpp", ".h", ".hpp",
    ".ipynb",
}

META_FILENAMES = {
    "pom.xml", "package.json", "package-lock.json", "pnpm-lock.yaml",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "project.yml", "tsconfig.json", "tsconfig.app.json",
    "vite.config.ts", "vite.config.js", "vite.config.mjs",
    "Cargo.toml", "go.mod", "build.gradle", "build.gradle.kts",
    "pyproject.toml", "requirements.txt",
}

LINE_THRESHOLD = 3


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # 不能 parse 就放行,不当门神

    tool = data.get("tool_name", "")
    if tool not in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        return 0

    inp = data.get("tool_input", {}) or {}
    file_path = inp.get("file_path", "")
    if not file_path:
        return 0

    if is_allowed(file_path):
        return 0

    if not is_business_file(file_path):
        return 0

    lines = count_changed_lines(tool, inp)
    if lines <= LINE_THRESHOLD:
        return 0

    log_block(file_path, lines, tool)
    sys.stderr.write(block_message(file_path, lines, tool))
    return 2


def is_allowed(file_path: str) -> bool:
    for sub in ALLOWLIST_PATH_SUBSTR:
        if sub in file_path:
            return True
    name = Path(file_path).name
    if name in ALLOWLIST_FILENAMES:
        return True
    suffix = Path(file_path).suffix.lower()
    if suffix in DOC_EXTENSIONS:
        return True
    return False


def is_business_file(file_path: str) -> bool:
    p = Path(file_path)
    if p.suffix.lower() in BUSINESS_EXTENSIONS:
        return True
    if p.name in META_FILENAMES:
        return True
    return False


def count_changed_lines(tool: str, inp: dict) -> int:
    """粗算改动行数。
    - Edit: max(new_string.lines, old_string.lines)
    - MultiEdit: 各 edit 的 max(new,old) 之和
    - NotebookEdit: new_source 行数（>阈值返回 999）
    - Write: 全文件视为大改动（返回 999），除非极短
    """
    if tool == "Edit":
        new_s = inp.get("new_string", "") or ""
        old_s = inp.get("old_string", "") or ""
        return max(line_count(new_s), line_count(old_s))
    if tool == "MultiEdit":
        total = 0
        for e in inp.get("edits", []) or []:
            new_s = e.get("new_string", "") or ""
            old_s = e.get("old_string", "") or ""
            total += max(line_count(new_s), line_count(old_s))
        return total
    if tool == "NotebookEdit":
        src = inp.get("new_source", "") or ""
        if line_count(src) <= LINE_THRESHOLD:
            return line_count(src)
        return 999
    # Write
    content = inp.get("content", "") or ""
    if line_count(content) <= LINE_THRESHOLD:
        return line_count(content)
    return 999


def line_count(s: str) -> int:
    if not s:
        return 0
    return s.count("\n") + (1 if s.strip() else 0)


def log_block(file_path: str, lines: int, tool: str) -> None:
    """把拦截记录追加到全局日志 ~/.rx/gatekeeper.log（失败静默，绝不影响拦截）。"""
    try:
        log_dir = os.path.expanduser("~/.rx")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(log_dir, "gatekeeper.log"), "a", encoding="utf-8") as f:
            f.write(f"{ts} | {tool} | {file_path} | {lines}行\n")
    except Exception:
        pass


def block_message(file_path: str, lines: int, tool: str) -> str:
    rel = file_path.replace(str(Path.home()), "~")
    return f"""🛑 Reasonix Gatekeeper — 业务代码改动被拦截

File: {rel}
Tool: {tool}  ·  改动 ~{lines} 行(超出例外阈值 {LINE_THRESHOLD} 行)

按 Reasonix 协作模式铁律:
  Claude = 大脑(出规格) · Reasonix = 手(改项目代码)
  例外仅在:≤ 3 行 + 单文件 + 不新增任何符号

此改动应走 reasonix 流:
  1. 写规格:.reasonix-tasks/<yyyymmdd>-<slug>.md(含 PROJECT_ROOT / 上下文 /
     参考实现 / 涉及文件 / 改动指令 / 完成判据 / 不得改动)
  2. dispatch:rx-go <规格> [预算]（或 /rx:go 走完整流程）
  3. 验证:编译 / 启动 / curl / 落库 4 步
  4. 失败回路 ≤ 3 次,超过即停下来找用户

若你确定本次确实属于例外(eg. typo / 端口号 / version bump):
  → 把改动拆到 ≤ 3 行的单次 Edit
  → 同一任务内例外动作 ≤ 1 次
  → 必须在回复中明说"绕过 reasonix(原因:xxx)"

若你认为本次拦截误判,可在对话中说明,用户决定是否例外通过。
"""


if __name__ == "__main__":
    sys.exit(main())

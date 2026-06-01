#!/usr/bin/env node
// rx-acp-dispatch — 通过 Reasonix ACP（Agent Client Protocol）派发规格任务。
//
// 为什么不是 `reasonix run`：run 模式只把工具调用作为文本流式输出，不真正执行，
// 文件永远不会落盘。ACP（stdio NDJSON JSON-RPC）才会真正驱动 write_file / run_command
// 等工具落地改动。
//
// 用法: node rx-acp-dispatch.mjs <project_root> <spec_file> <transcript> [budget] [model]
// 退出码: 0 = end_turn 正常完成；非 0 = 协议错误 / cancelled / 超时。

import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";

const [, , PROJECT_ROOT, SPEC_FILE, TRANSCRIPT, BUDGET, MODEL] = process.argv;

if (!PROJECT_ROOT || !SPEC_FILE || !TRANSCRIPT) {
  console.error("用法: rx-acp-dispatch.mjs <project_root> <spec_file> <transcript> [budget] [model]");
  process.exit(2);
}

const TASK = readFileSync(SPEC_FILE, "utf-8");

const args = ["acp", "--dir", PROJECT_ROOT, "--transcript", TRANSCRIPT];
if (BUDGET) args.push("--budget", BUDGET);
if (MODEL) args.push("--model", MODEL);

const child = spawn("reasonix", args, {
  stdio: ["pipe", "pipe", "inherit"],
  shell: process.platform === "win32",
  env: process.env,
});

let buf = "";
let nextId = 1;
const pending = new Map();

function send(method, params) {
  const id = nextId++;
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
  return new Promise((res) => pending.set(id, res));
}
function respond(id, result) {
  child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, result }) + "\n");
}

child.stdout.on("data", (chunk) => {
  buf += chunk.toString();
  let nl;
  while ((nl = buf.indexOf("\n")) >= 0) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (!line) continue;
    let m;
    try { m = JSON.parse(line); } catch { continue; }

    // agent → client：工具执行权限请求。editMode=auto/yolo 下 agent 本应自动放行，
    // 但这里仍显式批准，保证非交互管道不卡住。
    if (m.method === "session/request_permission") {
      const opts = m.params?.options || [];
      const allow = opts.find((o) => /allow/.test(o.optionId)) || opts[0];
      respond(m.id, { outcome: { outcome: "selected", optionId: allow?.optionId || "allow_always" } });
      continue;
    }
    // agent → client：进度通知。工具调用打印到 stderr（不污染 stdout 协议流）。
    if (m.method === "session/update") {
      const u = m.params?.update;
      if (u?.sessionUpdate === "tool_call") {
        process.stderr.write(`  [工具] ${u.title || u.kind || ""}\n`);
      } else if (u?.sessionUpdate === "agent_message_chunk") {
        process.stderr.write(u.content?.text || "");
      }
      continue;
    }
    // 对本端请求的响应
    if (m.id != null && pending.has(m.id)) {
      pending.get(m.id)(m);
      pending.delete(m.id);
    }
  }
});

child.on("error", (e) => {
  console.error("无法启动 reasonix:", e.message);
  process.exit(3);
});

const TIMEOUT_MS = 180000;
const timer = setTimeout(() => {
  console.error("\n[超时] ACP 派发超过 180s，强制终止");
  child.kill();
  process.exit(4);
}, TIMEOUT_MS);

(async () => {
  try {
    await send("initialize", { protocolVersion: 1, clientCapabilities: {} });

    const ns = await send("session/new", { cwd: PROJECT_ROOT, mcpServers: [] });
    const sid = ns.result?.sessionId;
    if (!sid) {
      console.error("session/new 失败:", JSON.stringify(ns.error || ns.result));
      clearTimeout(timer); child.kill(); process.exit(5);
    }

    const pr = await send("session/prompt", {
      sessionId: sid,
      prompt: [{ type: "text", text: TASK }],
    });
    const stop = pr.result?.stopReason;
    process.stderr.write(`\n[stopReason] ${stop}\n`);

    clearTimeout(timer);
    child.kill();
    process.exit(stop === "end_turn" ? 0 : 1);
  } catch (e) {
    console.error("ACP 派发异常:", e.message);
    clearTimeout(timer); child.kill(); process.exit(6);
  }
})();

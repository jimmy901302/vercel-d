/**
 * 麦门营养管家 · Vercel Serverless 代理
 * --------------------------------------------------
 * 与原仓库根目录 mcp-proxy.js 中的 POST /api/mcp 逻辑完全等价，
 * 但改造为 Vercel Serverless（Node.js runtime）形态：
 *   - 不再使用 http.createServer + listen（Serverless 无长驻进程）
 *   - Token 仅来自环境变量 MCD_MCP_TOKEN
 *     （Vercel 上没有 ~/.workbuddy/mcp.json，因此不读取本地配置文件，避免泄露）
 *   - 前端仍用相对地址 fetch("/api/mcp")，与本地 mcp-proxy.js 行为完全一致
 *
 * 请求：POST /api/mcp   body: { "name": <工具名>, "arguments": { ... } }
 * 响应：成功 { "ok": true, "structured": ..., "text": ..., "isError": ... }
 *       失败 { "ok": false, "error": "..." }
 */

const MCP_URL = "https://mcp.mcd.cn";

function loadToken() {
  if (process.env.MCD_MCP_TOKEN) {
    const t = String(process.env.MCD_MCP_TOKEN).trim();
    return t.startsWith("Bearer ") ? t : "Bearer " + t;
  }
  // 注意：Vercel 上不存在 ~/.workbuddy/mcp.json，这里仅作本地 vercel dev 的兼容，
  // 生产部署必须配置环境变量 MCD_MCP_TOKEN。
  const home = process.env.USERPROFILE || process.env.HOME;
  if (home) {
    try {
      const fs = require("fs");
      const path = require("path");
      const cfg = JSON.parse(
        fs.readFileSync(path.join(home, ".workbuddy", "mcp.json"), "utf8")
      );
      const hdr = cfg.mcpServers && cfg.mcpServers["mcd-mcp"] && cfg.mcpServers["mcd-mcp"].headers && cfg.mcpServers["mcd-mcp"].headers.Authorization;
      if (hdr) return hdr.startsWith("Bearer ") ? hdr : "Bearer " + hdr;
    } catch (e) {
      /* 配置文件缺失或解析失败 */
    }
  }
  return null;
}

const AUTH = loadToken();

async function callMcp(name, args) {
  if (!AUTH) {
    return {
      ok: false,
      error:
        "未配置 MCP Token：请在 Vercel 项目设置中添加环境变量 MCD_MCP_TOKEN（值为你的麦当劳开放平台 Token）。未配置时页面自动回退离线示例模式。",
    };
  }
  const body = JSON.stringify({
    jsonrpc: "2.0",
    id: Date.now(),
    method: "tools/call",
    params: { name: name, arguments: args || {} },
  });
  const resp = await fetch(MCP_URL, {
    method: "POST",
    headers: {
      Authorization: AUTH,
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    },
    body: body,
  });
  const text = await resp.text();
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch (e) {
    parsed = parseSSE(text);
  }
  if (parsed.error) {
    return {
      ok: false,
      error: (parsed.error && parsed.error.message) || "MCP 返回错误",
    };
  }
  const result = parsed.result || {};
  const contentText = (result.content || [])
    .map((c) => (typeof c.text === "string" ? c.text : ""))
    .join("\n");
  return {
    ok: true,
    structured: result.structuredContent || null,
    text: contentText,
    isError: !!result.isError,
  };
}

function parseSSE(text) {
  const lines = text.split("\n");
  let buf = "";
  for (const l of lines) {
    const t = l.trim();
    if (t.startsWith("data:")) buf += t.slice(5).trim();
  }
  if (buf) {
    try {
      return JSON.parse(buf);
    } catch (e) {
      /* ignore */
    }
  }
  return {};
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    // Vercel Node runtime 通常会预解析 JSON 到 req.body
    if (req.body !== undefined && req.body !== null) {
      if (Buffer.isBuffer(req.body)) return resolve(req.body.toString("utf8"));
      if (typeof req.body === "object") return resolve(req.body);
      return resolve(String(req.body));
    }
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}

module.exports = async (req, res) => {
  res.setHeader("Content-Type", "application/json; charset=utf-8");

  if (req.method !== "POST") {
    res.statusCode = 405;
    res.end(JSON.stringify({ ok: false, error: "仅支持 POST 方法" }));
    return;
  }

  let name, args;
  try {
    const raw = await readBody(req);
    const j = typeof raw === "object" ? raw : JSON.parse(raw);
    name = j.name;
    args = j.arguments;
  } catch (e) {
    res.statusCode = 400;
    res.end(JSON.stringify({ ok: false, error: "请求体不是合法 JSON" }));
    return;
  }

  if (!name) {
    res.statusCode = 400;
    res.end(JSON.stringify({ ok: false, error: "缺少工具名 name" }));
    return;
  }

  try {
    const r = await callMcp(name, args);
    res.statusCode = r.ok ? 200 : 502;
    res.end(JSON.stringify(r));
  } catch (e) {
    res.statusCode = 502;
    res.end(
      JSON.stringify({ ok: false, error: String((e && e.message) || e) })
    );
  }
};

/**
 * 麦门营养管家 · 本地 MCP 代理
 * --------------------------------------------------
 * 作用：持有麦当劳 MCP Token（仅存于本机），把浏览器对官方 MCP 的调用
 *       收敛到本机代理，避免 Token 泄露到前端、规避跨域(CORS)。
 *
 * 用法：
 *   node mcp-proxy.js            # 默认端口 8787
 *   PORT=9000 node mcp-proxy.js
 *
 * Token 来源（按优先级）：
 *   1. 环境变量 MCD_MCP_TOKEN
 *   2. ~/.workbuddy/mcp.json 中 mcpServers["mcd-mcp"].headers.Authorization
 *
 * 接口：
 *   GET  /                       -> index.html（游戏化参赛主页）
 *   GET  /<file>                 -> 静态文件（仅限本目录，含 demo-realtime.html）
 *   POST /api/mcp  {name, arguments} -> 返回 {ok, structured, text, isError}
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const MCP_URL = "https://mcp.mcd.cn";
const PORT = process.env.PORT || 8787;
const ROOT = __dirname;

function loadToken() {
  if (process.env.MCD_MCP_TOKEN) return "Bearer " + process.env.MCD_MCP_TOKEN;
  const home = process.env.USERPROFILE || process.env.HOME;
  const cfgPath = path.join(home, ".workbuddy", "mcp.json");
  try {
    const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
    const srv = cfg.mcpServers && cfg.mcpServers["mcd-mcp"];
    const hdr = srv && srv.headers && srv.headers.Authorization;
    if (hdr) return hdr.startsWith("Bearer ") ? hdr : "Bearer " + hdr;
  } catch (e) {
    /* 配置文件缺失或解析失败，稍后返回明确错误 */
  }
  return null;
}

const AUTH = loadToken();

async function callMcp(name, args) {
  if (!AUTH) {
    return {
      ok: false,
      error: "未找到 MCP Token：请配置 ~/.workbuddy/mcp.json 或环境变量 MCD_MCP_TOKEN",
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
    return { ok: false, error: (parsed.error && parsed.error.message) || "MCP 返回错误" };
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

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, "http://localhost");
  if (u.pathname === "/api/mcp" && req.method === "POST") {
    let body = "";
    for await (const ch of req) body += ch;
    let name, args;
    try {
      const j = JSON.parse(body);
      name = j.name;
      args = j.arguments;
    } catch (e) {
      res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ ok: false, error: "请求体不是合法 JSON" }));
      return;
    }
    if (!name) {
      res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ ok: false, error: "缺少工具名 name" }));
      return;
    }
    try {
      const r = await callMcp(name, args);
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(r));
    } catch (e) {
      res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
      res.end(
        JSON.stringify({
          ok: false,
          error: String((e && e.message) || e),
        })
      );
    }
    return;
  }

  // 静态文件
  let rel = u.pathname === "/" ? "/index.html" : u.pathname;
  const safe = path
    .normalize(rel)
    .replace(/^(\.\.[\/\\])+/, "")
    .replace(/^[/\\]+/, "");
  const fp = path.join(ROOT, safe);
  if (!fp.startsWith(ROOT)) {
    res.writeHead(403);
    res.end("forbidden");
    return;
  }
  fs.readFile(fp, (err, data) => {
    if (err) {
      res.writeHead(404);
      res.end("not found");
      return;
    }
    const ext = path.extname(fp).toLowerCase();
    res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log(
    `麦门营养管家实时代理已启动 -> http://localhost:${PORT}`
  );
  console.log(`MCP Token: ${AUTH ? "已加载(本机)" : "未找到，实时接口将返回错误"}`);
});

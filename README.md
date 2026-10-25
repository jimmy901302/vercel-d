# 麦门营养管家 · Vercel 部署说明

本目录是「麦门营养管家（McNutrition Assistant）」用于部署到 **Vercel** 的独立包。
它把「可联网的网页演示」所需的内容从原仓库中抽离、集中，并补上了 Vercel 所需的配置文件。
**原仓库里的任何文件均未被修改、移动或删除**——本目录内的文件全部是复制件或新建件。

> 作品本身：运行在 WorkBuddy 中的 Skill，通过麦当劳官方 MCP（`https://mcp.mcd.cn`）接入真实门店/营养/券数据。
> 本部署包提供其 **网页交互演示** 的线上版本：离线示例模式开箱即用；配置 Token 后可连官方实时数据。

---

## 1. 本次部署的技术形态（保持原技术栈）

| 项 | 说明 |
|---|---|
| 静态前端 | 原生 HTML/CSS/JS，**零框架、零 CDN、零构建**（`index.html` / `demo.html` / `demo-realtime.html` 均为单文件自包含） |
| 实时代理 | Node.js Serverless 函数 `api/mcp.js`，仅用内置模块 + 全局 `fetch`，**无第三方依赖** |
| 配置 | `vercel.json`（声明无构建、无框架、函数运行时） |
| 依赖清单 | `package.json`（依赖为空，仅声明 Node 引擎与本地启动脚本） |

未引入任何新框架或构建工具，完全沿用原仓库技术栈。

---

## 2. 文件清单（本目录包含的内容）

| 文件 / 目录 | 来源 | 用途 |
|---|---|---|
| `index.html` | 复制自根目录 | 🎮 游戏化参赛主页，**默认入口**。相对地址 `/api/mcp` 调代理 |
| `demo.html` | 复制自根目录 | 离线交互演示（无需 Token，浏览器直接算） |
| `demo-realtime.html` | 复制自根目录 | 实时版演示，相对地址 `/api/mcp` 调代理 |
| `mcp-proxy.js` | 复制自根目录 | 原本地代理，仅作**本地 parity / 参考**；Vercel 上真正生效的是 `api/mcp.js` |
| `api/mcp.js` | **新建** | Vercel Serverless 函数，等价于原代理的 `POST /api/mcp` |
| `skill/` | 复制自根目录（`skill/mcd-save-assistant/...`） | 原 WorkBuddy Skill 本体，为保持**相对路径结构**一并复制；部署时不执行，仅作静态资源/文档 |
| `MCP_INTEGRATION.md` | 复制自根目录 | MCP 接入说明（上下文参考） |
| `CONTEST_DECLARATION.md` | 复制自根目录 | 参赛声明（上下文参考） |
| `PROJECT_README.md` | 复制自根目录 `README.md` | 原项目说明（改名以免与本部署 README 冲突） |
| `package.json` | **新建** | 依赖清单（无第三方依赖） |
| `vercel.json` | **新建** | Vercel 部署配置 |
| `.gitignore` | **新建** | 标注忽略项，防止误提交密钥/产物 |
| `README.md` | **新建** | 本文件 |

> 复制件与原文件**字节一致**（除 `PROJECT_README.md` 为改名副本），未做任何内容改动；`api/mcp.js` 为针对 Serverless 重写，但请求/响应契约与原 `mcp-proxy.js` 完全一致。

---

## 3. 明确忽略的内容（不进入部署包）

以下文件/目录**刻意不复制**进 `vercel-deploy/`，请勿补回（尤其含密钥与本地配置者）：

| 忽略项 | 原因 |
|---|---|
| `node_modules/` | 本地依赖，Vercel 自动安装；本包零依赖，根本不应存在 |
| `.env` / `.env.*` / `*.local` | **本地环境变量 / 密钥**，含真实 Token 等，严禁提交或部署 |
| `~/.workbuddy/mcp.json` 及任何含 `MCD_MCP_TOKEN` 的文件 | **真实凭据来源**，绝不可进入仓库或部署包 |
| `verify-*.mjs`（`verify-index.mjs` 等 7 个） | 仅用于本地 headless Chrome 验证，非运行所需 |
| `_chrome_profile_*/`（8 个目录） | 浏览器自动化测试产物，体积大且含缓存，**与部署无关** |
| `static-test-server.js` | 本地静态预览辅助脚本，非运行所需 |
| `package.py` | 本地打包/zip 辅助脚本，非运行所需 |
| `workbuddy.md` | 开发对话记录，非运行所需 |
| `*.zip`（`mcd-save-assistant-contest_*.zip`）、`_verify_shot.png` | 归档/截图产物 |
| `logs`、`*.log` | 任何日志 |

> ⚠️ **本地配置泄露红线**：部署包里**任何位置**都不得出现真实 Token。Vercel 上的 Token 一律通过「环境变量」注入（见第 6 节），本目录的 `api/mcp.js` 也只读取环境变量，不读取本地 `mcp.json`。

---

## 4. 部署步骤

三种方式任选其一，效果相同。

### 方式 A：Vercel Dashboard 直接上传（最省事）
1. 进入 [vercel.com](https://vercel.com) → **Add New → Project**。
2. 选择 **「Upload」** 或「Drag and drop」，把本 `vercel-deploy/` 文件夹整体拖入。
3. Framework Preset 选 **「Other」**（因 `vercel.json` 已声明 `framework: null`）。
4. Build Command / Output Directory 留空（已由 `vercel.json` 设为 `null`）。
5. 展开 **Environment Variables**，添加 `MCD_MCP_TOKEN`（见第 6 节）。
6. 点击 **Deploy**。

### 方式 B：Git 仓库推送（推荐，便于迭代）
1. 把本 `vercel-deploy/` 目录作为**独立仓库**推送（或作为某个仓库的根目录）。
   ```bash
   cd vercel-deploy
   git init && git add -A && git commit -m "deploy: mcd nutrition assistant"
   git remote add origin <你的仓库地址>
   git push -u origin main
   ```
2. 在 Vercel Dashboard **Import Git Repository** 导入该仓库。
3. 配置项同上（Framework=Other，Build/Output 留空），并添加环境变量。
4. 之后每次 `git push` 自动部署。

### 方式 C：Vercel CLI
```bash
npm i -g vercel
cd vercel-deploy
vercel            # 按提示登录，首次部署为预览
vercel --prod     # 生产部署
# 环境变量可在 Dashboard 配置，或用：
vercel env add MCD_MCP_TOKEN
```
若用 CLI 且根目录不是本文件夹，用 `vercel deploy --cwd vercel-deploy`，或在 Vercel 项目设置里把 **Root Directory** 指向 `vercel-deploy/`。

---

## 5. 构建命令与输出目录

| 配置项 | 值 | 说明 |
|---|---|---|
| Build Command | **留空 / `null`** | 纯静态 + Serverless，无需构建 |
| Output Directory | **留空 / `null`** | 直接以本目录根作为站点根 |
| Install Command | 留空（或 `npm install`，无依赖，秒过） | `package.json` 无 dependencies |
| Node 版本 | `>=18`（Vercel 运行时 `nodejs22.x`） | 全局 `fetch` 可用 |

部署后：
- 站点根 `/` → `index.html`（游戏化主页）
- `/demo.html`、`/demo-realtime.html` → 对应演示页
- `/api/mcp` → Serverless 代理函数

---

## 6. 环境变量配置项

| 变量名 | 必填 | 说明 |
|---|---|---|
| `MCD_MCP_TOKEN` | 推荐（实时数据需要） | 你的麦当劳开放平台 Token（纯值，不含 `Bearer ` 前缀也会自动补全）。<br>获取：https://open.mcd.cn/mcp → 登录 → 控制台 → 激活 → 复制。<br>**不配置时页面自动回退离线示例模式，不影响访问。** |

配置位置：Vercel 项目 **Settings → Environment Variables**，作用域选 Production / Preview 均可。
**切勿**把 Token 写进代码或提交到仓库。

---

## 7. 部署限制与风险（必读）

### 7.1 路径引用是否失效
- ✅ 三份 HTML 均使用**相对根路径** `fetch("/api/mcp")`，且 CSS/JS/图标全部**内联**（`data:image/svg+xml` 或 `<style>`/`<script>` 内嵌），**没有任何外部相对资源文件**。因此部署到 Vercel 域名根不会失效。
- ⚠️ 页面内**提示文案**仍写着「运行 `node mcp-proxy.js`，用 `http://localhost:8787/` 打开」（这是原本地运行指引，属于纯文本提示，不影响功能）。若想更贴合线上，可把 `vercel-deploy/` 中的副本文案改为「实时数据由 Vercel 环境变量 `MCD_MCP_TOKEN` 提供」，属可选优化，**不影响运行**。

### 7.2 静态资源目录位置
- Vercel 把本目录**根**作为静态站点根，`index.html` 即首页。无需 `public/` 或 `dist/` 子目录。
- `skill/`、`*.md` 等会被当作静态文件原样托管（可访问），它们不含密钥，暴露无碍；若你希望完全不公开 `skill/`，可在 `vercel.json` 增加重写/拦截，或直接从部署包删除 `skill/`（网页演示不依赖它）。

### 7.3 文件大小限制
- 单静态文件上限约 **50 MB**（Hobby）/ 更大（Pro）；本包最大文件 `index.html` ≈ 119 KB，安全。
- Serverless 函数包（含依赖）上限约 **50 MB**；本函数零依赖、仅数 KB，安全。
- 单次请求/响应体上限约 **4.5 MB**（Hobby）；麦当劳 MCP 返回均为常规 JSON，远小于此。

### 7.4 本地配置文件 / 密钥泄露
- 🔴 **最高风险**：原 `mcp-proxy.js` 会读取 `~/.workbuddy/mcp.json` 取 Token；该文件在项目外、含真实凭据，**绝不可复制进部署包**。本 `api/mcp.js` 已改为**只读取环境变量** `MCD_MCP_TOKEN`，不再触碰 `mcp.json`。
- 提交前务必确认：部署包内无 `.env`、`mcp.json`、任何写死 Token 的字符串（原 `README` 等文档中的 `YOUR_MCP_TOKEN` 为占位符，安全）。
- Vercel 环境变量在传输/存储中加密，仅运行时注入函数进程，不会出现在前端代码里。

### 7.5 函数运行时与超时
- 函数 `maxDuration: 30s`、内存 256 MB（见 `vercel.json`），足以覆盖单次 MCP 调用。若麦当劳侧偶发慢响应，前端有 5s 探针超时并回退离线（见 `index.html` 的 `checkProxy`），不会卡死。
- Vercel 默认函数区域可能与麦当劳服务器地理距离较远，属正常网络延迟，非故障。

### 7.6 跨域（CORS）与跨域凭证
- 前端只与本 Vercel 域名的 `/api/mcp` 同源通信，由函数再转发到 `https://mcp.mcd.cn`，**Token 不出后端**，天然规避 CORS 与前端泄露——与原本地代理的安全模型一致。
- `create-order` 等会返回麦当劳官方 H5 支付链接，由 `window.open` 新标签打开，与部署平台无关。

### 7.7 其他
- 免费（Hobby）账号部署的站点为公开可访问；若演示含真实门店数据属公开信息，无隐私问题。
- 离线示例数据（`demo.html` 内嵌 / `skill/.../samples/`）为展示用途，不产生真实订单。

---

## 8. 本地联调（可选）

在 `vercel-deploy/` 目录内直接运行原代理即可复刻线上行为（需本机有 `~/.workbuddy/mcp.json` 或 `MCD_MCP_TOKEN` 环境变量）：

```bash
cd vercel-deploy
node mcp-proxy.js            # 默认 http://localhost:8787/ → 托管 index.html
# 浏览器打开 http://localhost:8787/ 验证实时数据
```

若想用 Vercel 本地模拟器：

```bash
npm i -g vercel
cd vercel-deploy
vercel dev                   # 启动本地 dev server，/api/mcp 由 api/mcp.js 提供
```

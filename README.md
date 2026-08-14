# SeaArt AI — Cloudflare Pages 云端文生图（免绑卡 · 24h 免费运行）

一个可直接运行的 AI 文生图 Web 应用：前端 HTML/JS 调用后端绘图接口，后端可切换 **智谱 AI（ZhipuAI）** 或 **Agnes AI** 两个绘图通道。
本项目已改造为 **Cloudflare Pages + Pages Functions**，可免费部署到云端，**不依赖你的电脑**，7×24 小时运行，其他人点击你分享的 `*.pages.dev` 网址即可免费生成图片。

> **免费无限制**：已彻底移除积分 / 付费墙逻辑，普通生图与 Boost HD 高清增强均可无限使用，不弹付费窗口、无额度限制。
> 未配置当前后端密钥时自动进入**演示模式**（返回示例图），保证全链路开箱即跑通。

## ⚠️ 模型选择（务必看）
后端通过模型名指定绘图模型，**必须是各厂商的【图像】模型**，文本模型不能出图：

| 厂商 | 图像模型（可绘图） | 文本/多模态模型（❌ 不能绘图） |
|------|-------------------|-------------------------------|
| 智谱 Zhipu | `cogview-3-flash`（高速，默认）、`cogview-3-plus`（高清） | `glm-4-flash` / `glm-4` / `glm-4v` |
| Agnes AI | `agnes-image-2.0-flash`（图生图专精）、`agnes-image-2.1-flash`（高信息密度） | `agnes-2.0-flash`（文本） |

> 不要把 `glm-4-flash` / `agnes-2.0-flash` 等文本模型当作绘图模型，否则生图会失败并自动回退示例图。

## 双后端对比

| 维度 | 智谱 AI（ZhipuAI） | Agnes AI |
|------|-------------------|----------|
| 接口 | `POST {LLM_BASE_URL}images/generations` | `POST {AGNES_BASE_URL}/images/generations`（OpenAI 兼容） |
| 默认基地址 | `https://open.bigmodel.cn/api/paas/v4/` | `https://apihub.agnes-ai.com/v1` |
| 推荐模型 | `cogview-3-flash` / `cogview-3-plus` | `agnes-image-2.0-flash` / `agnes-image-2.1-flash` |
| 支持尺寸 | 1024x1024 / 1440x720 / 720x1440 | 1024x1024 / 1024x768 / 768x1024 |
| 超分(upscale) | Boost HD 高清增强 + 取最大尺寸 | Boost HD 高清增强 + 取最大尺寸 |
| 计费 | 按量 / 额度 | 当前图像接口免费 |
| 切换方式 | `DRAW_BACKEND=zhipu`（默认） | `DRAW_BACKEND=agnes` |

两个后端共享同一套前端与接口契约，切换 `DRAW_BACKEND` 即可，无需改动 `index.html`。

## 目录结构

```
SeaArt-AI-Project/
├── frontend/
│   └── index.html          # 前端页面（含生图/画廊/下载，无需改动）
├── functions/              # Cloudflare Pages Functions（云端后端，JS 实现）
│   ├── _shared/
│   │   └── utils.js        # 双绘图后端核心逻辑（尺寸映射 / HD 增强 / 演示兜底 / 代理）
│   └── api/
│       ├── health.js       # GET  /api/health   健康检查
│       ├── generate.js     # POST /api/generate 生图
│       ├── boost.js        # POST /api/boost    Boost HD 高清增强
│       ├── proxy_image.js  # GET  /api/proxy_image?url=  CORS 安全图片代理
│       └── demo.js         # GET  /api/demo?prompt=&hd=1  演示模式示例图
├── package.json            # 声明 ES Module（Cloudflare Functions 需要）
├── start.bat               # （本地开发可选）启动本地 Flask 后端
├── start.sh
└── README.md
```

> 本地开发仍可选用 `backend/app.py`（Python/Flask）；**云端部署只使用 `frontend/` + `functions/`**，不再需要 Docker / 容器 / 绑卡。

## 接口说明

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/api/health` | 健康检查，返回 `backend`(当前后端)、`mode: zhipu\|agnes\|demo`、`model` |
| POST | `/api/generate` | 生图。入参 `{prompt, neg, w, h, upscale?, superres?, seed?}`，返回 `{ok, img_url, mode, size, params}` |
| POST | `/api/boost` | **Boost HD 高清增强**。入参 `{prompt, neg, w, h, upscale(1~4), superres(bool), seed?}`，返回高清图 URL |
| GET  | `/api/proxy_image?url=` | CORS 安全的图片下载代理 |
| GET  | `/api/demo?prompt=&hd=1` | 演示模式示例图（SVG，hd=1 标注高清） |

## 前端 → 后端 数据流
1. 填写 Prompt，点击 Generate → 前端 `POST /api/generate`
2. 后端按 `DRAW_BACKEND` 调用智谱或 Agnes 绘图接口 → 返回图片 URL
3. 图片加载进画廊；点击 SD/HD 下载按钮 → 前端通过 `/api/proxy_image` 拉取并下载

> 说明：两厂商原生分辨率上限不同（见上表）。Boost HD 的「4 倍超分」通过 **HD 提示词增强 + 取最大支持尺寸** 等价实现（非像素级 4× 拉伸），`upscale` 参数仍完整保留并驱动超分增强。任一接口异常均自动回退演示图，页面不崩溃。

---

## 云端部署（Cloudflare Pages · 免费 · 免绑卡 · 7×24 运行）

本项目已改写为 Cloudflare Pages 静态前端 + Pages Functions，可免费部署，**无需信用卡**，且天然 7×24 在线。

### 改动说明（已就绪）
- `frontend/index.html`：`API_BASE = ""`（相对路径，自动适配任意域名 / `*.pages.dev`）。
- `functions/`：用 JavaScript 完整复刻了原 Flask 后端的双绘图后端、尺寸映射、HD 增强、演示兜底与图片代理逻辑，运行在 Cloudflare Edge。
- `package.json`：声明 `"type": "module"`，Pages Functions 以 ES Module 方式加载。
- 密钥安全：真实 Key **不在仓库里**；云端请在 Cloudflare 控制台填写环境变量。

### 部署步骤（约 5 分钟）

1. **确保本仓库已推送到 GitHub**（仓库名如 `seaart-ai`，公开或私有均可）。
2. 打开 [Cloudflare Dashboard](https://dash.cloudflare.com) → 左侧 **Workers & Pages** → 右上角 **Create** → 选 **Pages** → **Connect to Git**。
3. 授权并选择你的 GitHub 仓库 `seaart-ai`。
4. 在 **Set up builds and deployments** 配置：
   - **Project name**：`seaart-ai`（可自定）
   - **Production branch**：`main`
   - **Framework preset**：`None`
   - **Build command**：**留空**（无需构建）
   - **Build output directory**：填 `frontend`（静态前端所在目录）
5. 先点击 **Save and Deploy**（先部署一版，环境变量稍后补）。
6. 部署完成后，进入项目 **Settings → Environment variables**，添加以下变量（选填；不填则进入演示模式）：
   - `LLM_API_KEY` = 你的智谱 Key
   - `AGNES_API_KEY` = 你的 Agnes Key
   - `DRAW_BACKEND` = `zhipu`（默认）或 `agnes`
   - （可选）`LLM_MODEL` / `AGNES_MODEL` / `LLM_BASE_URL` / `AGNES_BASE_URL` 覆盖默认值
7. 改完变量后，回到 **Deployments** 页，对最新一次部署点 **Retry / Redeploy** 让变量生效。
8. 打开形如 `https://seaart-ai.pages.dev` 的地址即可使用，把这个链接发给别人即可免费生图。

> **自定义域名（可选）**：因为你已在 Cloudflare，进入项目 **Custom domains** 添加你的子域名（如 `app.yourname.com`），Cloudflare 会自动下发证书与 DNS，无需额外绑卡。

### 本地预览（可选）
```bash
npm install -g wrangler
wrangler pages dev --project=seaart-ai .
```

---

## 本地运行（Flask 开发版，可选）

若想在本地用 Python/Flask 跑同一套前端（不部署云端时）：

```bash
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env   # 填入密钥；不填则演示模式
DRAW_BACKEND=zhipu python backend/app.py   # 或 DRAW_BACKEND=agnes
# 浏览器访问 http://127.0.0.1:5000
```

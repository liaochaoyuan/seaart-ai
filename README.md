# SeaArt AI — 本地 Python 后端版（Flask + 双绘图后端：智谱 AI / Agnes AI）

一个可直接运行的 AI 文生图 Web 应用：前端 HTML/JS 调用本地 Flask 后端，后端可切换 **智谱 AI（ZhipuAI）** 或 **Agnes AI** 两个绘图通道，
并自动开启 CORS 跨域。未配置当前后端密钥时自动进入**演示模式**（返回示例图），保证全链路开箱即跑通。

> **本版本为本地免费版**：已彻底移除积分 / 付费墙逻辑，普通生图与 Boost HD 高清增强均可无限使用，不弹付费窗口、无额度限制。

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
├── backend/
│   ├── app.py              # Flask 后端（CORS + 双绘图后端 + 图片代理 + 演示兜底）
│   ├── requirements.txt    # 依赖：flask / flask-cors / requests / zhipuai
│   └── .env.example        # 双后端配置模板（智谱 + Agnes 全套密钥 + 切换开关）
├── start.bat               # Windows 一键启动
├── start.sh                # Linux/macOS 一键启动
└── README.md
```

## 快速开始

### 1. 安装依赖
```bash
pip install -r backend/requirements.txt
```

### 2. 配置（复制模板并修改）
```bash
cp backend/.env.example backend/.env
```
填入你的密钥，并按需设置 `DRAW_BACKEND`（见下）。不配置则自动进入演示模式。

### 3. 切换绘图后端（核心）
通过环境变量 `DRAW_BACKEND` 选择通道（默认 `zhipu`）：

```bash
# 使用智谱 AI（默认）
DRAW_BACKEND=zhipu python backend/app.py

# 使用 Agnes AI
DRAW_BACKEND=agnes python backend/app.py
```

- **智谱**：确保 `LLM_MODEL` 为 `cogview-3-flash` / `cogview-3-plus`。
- **Agnes**：确保 `AGNES_MODEL` 为 `agnes-image-2.0-flash` / `agnes-image-2.1-flash`（**不要**用文本模型 `agnes-2.0-flash`）。

启动后访问 **http://127.0.0.1:5000** 即可使用。

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

## 云端部署（Render · 免费 24h 运行 · 可绑 .com 域名）

本项目已容器化，可部署到 [Render](https://render.com) 免费档，**不依赖你的电脑**，云端 7×24 运行。前端 `API_BASE` 已改为相对路径，后端由 Flask 同源托管，`ProxyFix` 已启用，可直接挂自定义域名。

### 改动说明（已就绪）
- `Dockerfile`：基于 `python:3.12-slim`，安装依赖后 `python backend/app.py`，监听 `0.0.0.0:${PORT}`。
- `render.yaml`：声明为 Docker Web 服务，`healthCheckPath: /api/health`，`DRAW_BACKEND=zhipu`。
- `frontend/index.html`：`API_BASE = ""`（相对路径，适配任意域名）。
- 密钥安全：`app.py` 与 `.env.example` 中**已不再写入真实 Key**；真实密钥仅存在于被 `.gitignore` 忽略的 `backend/.env`（本地用），云端请在 Render 控制台填写。

### 部署步骤
1. 将本仓库推送到 GitHub（仓库名如 `seaart-ai`）。
2. 打开 [render.com](https://render.com) → 用 GitHub 登录 → **New → Web Service** → 选择该仓库。
3. Render 自动读取 `render.yaml`（Docker 构建）。在 **Environment** 中补填两个私密变量：
   - `LLM_API_KEY` = 你的智谱 Key
   - `AGNES_API_KEY` = 你的 Agnes Key
   （`DRAW_BACKEND` 已默认 `zhipu`，可改 `agnes`）
4. 点击 **Deploy**，等待构建完成，得到形如 `https://seaart-ai.onrender.com` 的地址。
5. **绑定 .com 子域名**（如 `app.yourname.com`）：在域名 DNS 添加一条 **CNAME** 记录，主机名 `app` → 目标 `seaart-ai.onrender.com`；再到 Render 控制台 **Settings → Custom Domains** 添加 `app.yourname.com` 并验证。

> 免费档说明：Render 免费实例在闲置后会有约 30–50 秒冷启动（首次访问稍慢），之后恢复正常；如需常驻可升级付费档。

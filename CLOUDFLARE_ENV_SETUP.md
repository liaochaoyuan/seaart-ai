# SeaArt AI · 在 Cloudflare 填入 API Key（从演示模式切换到真实生图）

> 目标：让 `https://seaart-ai.pages.dev` 从「演示示例图」变成「真实 AI 生图」。

---

## 一、为什么现在是演示图？

后端逻辑：`DEMO_MODE = not bool(活跃密钥)`。
Cloudflare 控制台没填 `LLM_API_KEY` / `AGNES_API_KEY` 时，系统自动返回示例图（SVG），页面不报错但生不出真实图。

填了真实 Key 后，`DEMO_MODE=false`，走真实绘图接口。

---

## 二、你的真实 Key 在哪

本地文件（不入库、仅你本机）：
```
G:/workbuddy/完成的任务文件/backend/.env
```

用记事本打开它，可以看到这些行（只复制 `=` 右边的值）：

```bash
DRAW_BACKEND=zhipu
LLM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   ← 复制这串
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_MODEL=cogview-3-flash
AGNES_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxx      ← 复制这串
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
AGNES_MODEL=agnes-image-2.0-flash
```

---

## 三、填到 Cloudflare 控制台（约 2 分钟）

1. 打开 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 左侧 **Workers & Pages** → 点项目 **seaart-ai**
3. 顶部 **设置（Settings）** → 左侧 **环境变量（Environment variables）**
4. 点 **添加变量（Add variable）**，逐条添加（值从 `.env` 复制，**只填值，不填变量名以外的东西**）：

| 变量名（Name） | 值（Value，从 .env 复制） |
|----------------|---------------------------|
| `DRAW_BACKEND` | `zhipu`（或 `agnes`） |
| `LLM_API_KEY`  | `.env` 里 `LLM_API_KEY=` 后面那串 |
| `AGNES_API_KEY`| `.env` 里 `AGNES_API_KEY=` 后面那串 |

> 说明：`LLM_BASE_URL` / `LLM_MODEL` / `AGNES_BASE_URL` / `AGNES_MODEL` **不用填**，代码已用默认值；只要填上面 3 个即可。

5. 每条添加后点 **保存（Save）**。

---

## 四、重新部署让变量生效

1. 回到项目页面顶部 **部署（Deployments）**
2. 找到最新一次部署，点右侧 **⋯ / Retry deployment（重新部署）**
3. 等 30 秒～1 分钟，状态变 **Success / Active**

---

## 五、验证是否成功

1. 刷新 `https://seaart-ai.pages.dev`
2. 输入一个英文 Prompt（例：`a cute cat, oil painting style`），点 **Generate**
3. 成功标志：返回真实图片（不是渐变 SVG 示例图）
4. 也可以访问：
   ```
   https://seaart-ai.pages.dev/api/health
   ```
   返回里 `"demo": false` 且 `"backend": "zhipu"` 即表示 Key 已生效。

---

## 六、如果还不行（排查）

- 仍显示示例图 → 检查 `LLM_API_KEY` 是否复制完整（末尾别漏字符）；确认已 **Redeploy**。
- 报红 / 超时 → 在群里发截图，我帮你查 `/api/health` 返回信息。

---

## 七、（可选）绑自己的域名，利于谷歌收录

1. 项目页 **自定义域（Custom domains）** → 输入你的子域名，例如：
   ```
   app.yourdomain.com
   ```
2. 你域名本身已在 Cloudflare，会自动下发 HTTPS 证书 + 自动配 DNS。
3. 生效后用 `https://app.yourdomain.com` 访问，这个独立域名对 SEO / 爬虫更友好。

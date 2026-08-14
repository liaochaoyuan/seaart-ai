"""
SeaArt AI - Flask 后端
- 端口: 5000（可通过环境变量 PORT 修改）
- 监听: 0.0.0.0（可通过环境变量 HOST 修改，默认 0.0.0.0，适配域名/反向代理部署）
- 跨域: 对 /api/* 自动开启 CORS (flask-cors)，前端 file:// 或任意源均可调用
- 绘图后端: 支持双通道，由环境变量 DRAW_BACKEND 切换（默认 zhipu）
    • zhipu  -> 智谱 AI (BigModel / ZhipuAI)  CogView 图像系列
                POST {LLM_BASE_URL}images/generations   模型 cogview-3-flash / cogview-3-plus
    • agnes  -> Agnes AI (apihub.agnes-ai.com) 图像模型
                POST {AGNES_BASE_URL}/images/generations  模型 agnes-image-2.0-flash / agnes-image-2.1-flash
- 兜底: 未配置当前后端密钥 或 调用异常（密钥失效 / 模型不支持 / 超时）时，
        自动回退到演示示例图（mode="demo"），保证全链路不中断、页面不崩溃。
- 无限制: 后端不做任何免费次数 / 积分额度校验，生图无次数限制

=====================================================================
 模型选择（重要）
=====================================================================
 智谱 Zhipu:   cogview-3-flash / cogview-3-plus  = 【图像】模型，可出图
               ⚠️ glm-4-flash / glm-4 / glm-4v   = 【文本 / 多模态】模型，不能绘图
 Agnes AI:     agnes-image-2.0-flash / agnes-image-2.1-flash = 【图像】模型，可出图
               ⚠️ agnes-2.0-flash                = 【文本】模型，不能绘图（切勿当作绘图模型）

=====================================================================
 Boost HD 高清增强 参数说明
=====================================================================
POST /api/boost  (普通生图也可在 /api/generate 中带 upscale/superres 触发)

请求体 (JSON):
  prompt    str   画面提示词（已含风格后缀）
  neg       str   反向提示词
  w, h      int   基准宽高（自动按当前后端支持的尺寸映射到最近比例）
  upscale   int   高清倍率，默认 2，范围 1~4（驱动超分语义增强，接口兼容）
  superres  bool  超分开关，默认 true -> 在提示词注入「超分辨率/8k/极致细节」，
                       反向词注入「模糊/低分辨率/锯齿/压缩伪影」
  seed      int   可选随机种子（透传给后端，保证可复现）

后端处理:
  1. 按宽高比把请求尺寸映射到当前后端支持的标准尺寸
     (智谱: 1024x1024 / 1440x720 / 720x1440；Agnes: 1024x1024 / 1024x768 / 768x1024)；
  2. 超分时对 prompt / negative_prompt 做高清语义增强;
  3. 调用对应后端绘图接口（智谱优先 zhipuai SDK 再 REST；Agnes 走 OpenAI 兼容 REST）;
  4. 任意异常时自动返回演示示例图;
  5. 返回 {ok, img_url, mode, size:{w,h}, params:{upscale,superres}}。

演示模式(无 Key 或调用失败) 自动返回标注 HD 的示例 SVG，验证全链路不中断。
=====================================================================
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from urllib.parse import quote, unquote

import requests
from flask import (
    Flask, request, jsonify, Response, send_from_directory
)
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

# 线程池：将阻塞式的绘图调用放入后台线程，提升大图高清生成的并发稳定性
executor = ThreadPoolExecutor(max_workers=4)

# HD 默认与边界参数
DEFAULT_UPSCALE = 2
MIN_UPSCALE = 1
MAX_UPSCALE = 4


def _load_env_file():
    """极简 .env 加载（不依赖 python-dotenv）。"""
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()

# ===== 绘图后端切换 =====
# DRAW_BACKEND: zhipu(默认) | agnes
DRAW_BACKEND = os.environ.get("DRAW_BACKEND", "zhipu").lower()

# ===== 智谱 AI (ZhipuAI / BigModel) 配置 =====
#   LLM_MODEL 必须是 CogView 系列【图像】模型：
#     • cogview-3-flash  -> 高速（默认）
#     • cogview-3-plus   -> 高质量 / 高清（Boost HD 首选）
#   ⚠️ glm-4-flash / glm-4 / glm-4v 等为【文本 / 多模态】模型，不能调用绘图接口。
LLM_API_KEY = os.environ.get(
    "LLM_API_KEY", ""
)
LLM_BASE_URL = os.environ.get(
    "LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"
)
LLM_MODEL = os.environ.get("LLM_MODEL", "cogview-3-flash")

# ===== Agnes AI (apihub.agnes-ai.com) 配置 =====
#   AGNES_MODEL 必须是【图像】模型：
#     • agnes-image-2.0-flash -> 文生图主力（已验证可出图，支持 seed、negative_prompt）
#     • agnes-image-2.1-flash -> 纯文生图、高信息密度更优
#   ⚠️ agnes-2.0-flash 是【文本】模型，不能调用 /images/generations，误用会回退演示图。
#   内置默认值采用可出图的 agnes-image-2.0-flash（与智谱默认改为 cogview-3-flash 同理）。
#   Agnes 接口基于 litellm，不支持 response_format 等参数——_post_agnes 已做自动剔除+重试。
AGNES_API_KEY = os.environ.get(
    "AGNES_API_KEY", ""
)
AGNES_BASE_URL = os.environ.get(
    "AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1"
)
AGNES_MODEL = os.environ.get("AGNES_MODEL", "agnes-image-2.0-flash")


def _active_key():
    """返回当前绘图后端对应的 API Key。"""
    if DRAW_BACKEND == "agnes":
        return AGNES_API_KEY
    return LLM_API_KEY


def _active_model():
    return AGNES_MODEL if DRAW_BACKEND == "agnes" else LLM_MODEL


# 演示模式：当前后端未配置密钥时触发
DEMO_MODE = not bool(_active_key())


app = Flask(__name__, static_folder=None)
# 对 API 路由开启跨域，允许前端以 file:// 或任意源访问
CORS(app, resources={r"/api/*": {"origins": "*"}})
# 域名/反向代理部署支持：信任 X-Forwarded-* 头，使 request.url_root 正确反映公网域名
# （本地直连无这些头时不产生影响）
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def clamp_dim(v, lo=512, hi=2048):
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = 512
    v = max(lo, min(hi, v))
    return max(lo, (v // 8) * 8)  # 对齐到 8 的倍数


def _map_size(w, h, backend="zhipu", hd=False):
    """将任意宽高比映射到对应后端支持的标准尺寸。

    hd=True（Boost HD）时优先选择该比例下的最大可用尺寸，以体现高清超分。
    各后端原生分辨率上限不同：
      • 智谱 : 1024x1024 / 1440x720 / 720x1440
      • Agnes: 1024x1024 / 1024x768 / 768x1024
    「4 倍超分」通过 HD 提示词增强 + 取最大支持尺寸 等价实现（非像素级 4× 拉伸）。
    """
    try:
        w = int(w) or 1024
        h = int(h) or 1024
    except (TypeError, ValueError):
        return "1024x1024"
    ar = (w / h) if h else 1.0
    if backend == "agnes":
        if 0.8 <= ar <= 1.25:
            return "1024x1024"      # 近似 1:1
        if ar > 1.25:
            return "1024x768"       # 横图（覆盖 16:9 / 4:3 等，hd 取最大）
        return "768x1024"           # 竖图（覆盖 9:16 等，hd 取最大）
    # zhipu
    if 0.8 <= ar <= 1.25:
        return "1024x1024"          # 近似 1:1（智谱最大方图）
    if ar > 1.25:
        return "1440x720"           # 横图 2:1（覆盖 16:9 / 4:3 等，hd 取最大）
    return "720x1440"               # 竖图 1:2（覆盖 9:16 等，hd 取最大）


def _hd_enhance(prompt, neg, superres):
    """超分语义增强：向 prompt / negative_prompt 注入高清重建关键词。"""
    if not superres:
        return prompt, neg
    hd_pos = "，超高清，8k分辨率，极致细节，超分辨率重建，锐利清晰，高保真"
    hd_neg = "，模糊，低分辨率，锯齿，压缩伪影，涂抹感"
    return (prompt + hd_pos), (neg + hd_neg)


def _extract_image_url(resp):
    """兼容 SDK 返回对象与 REST JSON dict 两种方式提取图片 URL。"""
    data = getattr(resp, "data", None)
    if data is None and isinstance(resp, dict):
        data = (resp or {}).get("data")
    if not data:
        return None
    first = data[0]
    if isinstance(first, dict):
        return first.get("url") or first.get("b64_json")
    return getattr(first, "url", None) or getattr(first, "b64_json", None)


# --------------------------------------------------------------------------
# 后端 1：智谱 AI (ZhipuAI)
# --------------------------------------------------------------------------
def _post_zhipu(prompt, neg, w, h, seed=None, timeout=120, hd=False):
    """调用智谱 AI 绘图接口（images/generations），优先官方 SDK，异常回退 REST 直连。

    兼容 CogView 系列图像模型（cogview-3-flash / cogview-3-plus 等）。
    hd=True 时按 Boost HD 逻辑取最大支持尺寸。
    """
    size = _map_size(w, h, backend="zhipu", hd=hd)
    # 智谱绘图对 negative_prompt 支持有限，正向下统一并入提示词更稳妥
    gen_prompt = prompt
    if neg:
        gen_prompt = f"{prompt}（避免：{neg}）"
    sdk_err = None

    # 1) 官方 SDK 路径
    try:
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        kwargs = {"model": LLM_MODEL, "prompt": gen_prompt, "size": size}
        if seed is not None:
            kwargs["seed"] = int(seed)
        resp = client.images.generations(**kwargs)
        url = _extract_image_url(resp)
        if url:
            return url
        raise RuntimeError("智谱返回中未包含图片地址")
    except Exception as e:  # noqa: BLE001
        sdk_err = e

    # 2) REST 直连兜底（独立异常，便于暴露真实失败原因）
    try:
        url = LLM_BASE_URL.rstrip("/") + "/images/generations"
        payload = {"model": LLM_MODEL, "prompt": gen_prompt, "size": size, "n": 1}
        if neg:
            payload["negative_prompt"] = neg
        if seed is not None:
            payload["seed"] = int(seed)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        }
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
        r.raise_for_status()
        d = r.json()
        data = d.get("data") or []
        if data and (data[0].get("url") or data[0].get("b64_json")):
            return data[0].get("url") or data[0].get("b64_json")
        raise RuntimeError(d.get("msg") or "智谱返回中未包含图片地址")
    except Exception as e:  # noqa: BLE001
        raise e if sdk_err is None else e


# --------------------------------------------------------------------------
# 后端 2：Agnes AI (apihub.agnes-ai.com) — OpenAI 兼容 /images/generations
# --------------------------------------------------------------------------
def _post_agnes(prompt, neg, w, h, seed=None, timeout=120, hd=False):
    """调用 Agnes AI 绘图接口（OpenAI 兼容 /images/generations）。

    模型须为图像模型：agnes-image-2.0-flash / agnes-image-2.1-flash。
    hd=True 时按 Boost HD 逻辑取最大支持尺寸。
    返回图片 URL 字符串；任意异常向上抛出，由 generate_image 统一兜底为演示图。

    兼容性说明（关键）：
      Agnes 接口基于 litellm 网关，部分 OpenAI 风格参数（如 response_format）
      不被底层 t2i 模型支持，会返回 400 UnsupportedParamsError。
      这里采用「自动剔除 + 重试」策略：命中该错误时，从 payload 中移除被点名的参数
      并重试（最多 3 次），从而对任意后端参数差异保持鲁棒；网络超时同样重试。
    """
    size = _map_size(w, h, backend="agnes", hd=hd)
    gen_prompt = prompt
    if neg:
        gen_prompt = f"{prompt}（避免：{neg}）"

    url = AGNES_BASE_URL.rstrip("/") + "/images/generations"
    # 仅发送 Agnes 明确支持的核心参数；不支持的参数会被下面的重试逻辑自动剔除
    payload = {
        "model": AGNES_MODEL,
        "prompt": gen_prompt,
        "size": size,
        "n": 1,
    }
    if neg:
        payload["negative_prompt"] = neg
    if seed is not None:
        payload["seed"] = int(seed)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AGNES_API_KEY}",
    }

    last_err = "Agnes 调用失败"
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                d = r.json()
                data = d.get("data") or []
                if data and (data[0].get("url") or data[0].get("b64_json")):
                    return data[0].get("url") or data[0].get("b64_json")
                raise RuntimeError(
                    d.get("msg") or d.get("error") or d.get("message")
                    or "Agnes 返回中未包含图片地址"
                )
            # 非 200：尝试解析是否因「不支持的参数」导致，自动剔除后重试
            body = {}
            try:
                body = r.json()
            except Exception:  # noqa: BLE001
                pass
            err_obj = body.get("error") if isinstance(body, dict) else None
            msg = str(
                (err_obj or {}).get("message")
                or body.get("message")
                or body.get("error")
                or r.text
            )
            dropped = re.findall(r"Setting `(\w+)` is not supported", msg)
            if dropped and any(k in payload for k in dropped):
                for k in dropped:
                    payload.pop(k, None)
                last_err = msg
                continue
            raise RuntimeError(msg[:300])
        except requests.exceptions.Timeout:
            # 大图高清生成偶发超时：重试一次
            last_err = "Agnes 请求超时（已重试）"
            continue
    raise RuntimeError(last_err[:300])


def _post_draw(prompt, neg, w, h, seed=None, timeout=120, hd=False):
    """按 DRAW_BACKEND 分发到对应后端绘图实现。"""
    if DRAW_BACKEND == "agnes":
        return _post_agnes(prompt, neg, w, h, seed=seed, timeout=timeout, hd=hd)
    return _post_zhipu(prompt, neg, w, h, seed=seed, timeout=timeout, hd=hd)


def _run_blocking(fn, timeout):
    """在线程池中执行阻塞调用，统一超时处理。"""
    fut = executor.submit(fn)
    try:
        return fut.result(timeout=timeout)
    except FuturesTimeout:
        fut.cancel()
        raise RuntimeError(f"生图超时（>{timeout}s），请降低分辨率或稍后重试")
    except Exception:  # noqa: BLE001
        raise


def _demo_img_url(prompt):
    return (
        request.url_root.rstrip("/")
        + "/api/demo?hd=1&prompt="
        + quote((prompt or "")[:60])
    )


def generate_image(prompt, neg, w, h, boost=False, upscale=DEFAULT_UPSCALE,
                   superres=True, seed=None):
    """
    统一生图入口。
    - boost=True 时做超分语义增强，使用更长超时。
    - 返回 (img_url, size_dict, params_dict, mode)；mode 为 "zhipu"/"agnes"/"demo"。
    - 未配置当前后端密钥或调用异常时，自动回退到演示示例图（mode="demo"）。
    """
    upscale = max(MIN_UPSCALE, min(MAX_UPSCALE, int(upscale or DEFAULT_UPSCALE)))
    if boost:
        prompt, neg = _hd_enhance(prompt, neg, superres)
        w = clamp_dim(int(w) * upscale)
        h = clamp_dim(int(h) * upscale)
        timeout = 180  # 大图高清生成耗时更长
    else:
        w = clamp_dim(w)
        h = clamp_dim(h)
        timeout = 120

    meta = {"upscale": upscale, "superres": superres}

    if DEMO_MODE:
        return _demo_img_url(prompt), {"w": w, "h": h}, meta, "demo"

    # 已配置密钥：尝试真实生图，任意异常自动回退演示图
    try:
        img_url = _run_blocking(
            lambda: _post_draw(prompt, neg, w, h, seed=seed, timeout=timeout, hd=boost),
            timeout + 10,
        )
        return img_url, {"w": w, "h": h}, meta, DRAW_BACKEND
    except Exception as e:  # noqa: BLE001
        img_url = _demo_img_url(prompt)
        meta = dict(meta)
        meta["fallback"] = True
        meta["reason"] = str(e)[:200]
        return img_url, {"w": w, "h": h}, meta, "demo"


def build_demo_svg(prompt, hd=False):
    safe = (prompt or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    tag = "SeaArt Demo HD" if hd else "SeaArt Demo"
    note = (
        "演示模式示例图 (HD)" if hd else
        "未配置密钥 / 接口异常 / 误用文本模型(glm-4-flash, agnes-2.0-flash) — 演示示例图"
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="768" height="768">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#a78bfa"/>'
        '<stop offset="100%" stop-color="#ffd066"/></linearGradient></defs>'
        '<rect width="768" height="768" fill="url(#g)"/>'
        f'<text x="384" y="360" font-size="34" fill="#0c0c12" text-anchor="middle" '
        f'font-family="sans-serif" font-weight="bold">{tag}</text>'
        f'<text x="384" y="410" font-size="20" fill="#1a1a2e" text-anchor="middle" '
        f'font-family="sans-serif">{safe[:40]}</text>'
        f'<text x="384" y="700" font-size="14" fill="#1a1a2e" text-anchor="middle" '
        f'font-family="sans-serif">{note}</text>'
        '</svg>'
    )


def err(msg, code="GEN_FAILED", http=500):
    return jsonify(ok=False, msg=msg, code=code), http


@app.route("/api/health")
def health():
    return jsonify(
        ok=True,
        backend=DRAW_BACKEND,
        mode="demo" if DEMO_MODE else DRAW_BACKEND,
        demo=DEMO_MODE,
        model=_active_model(),
        msg=(
            f"demo mode (no API key for {DRAW_BACKEND})" if DEMO_MODE
            else f"{DRAW_BACKEND} ready"
        ),
    )


@app.route("/api/generate", methods=["POST"])
def generate():
    try:
        body = request.get_json(force=True, silent=True) or {}
        prompt = (body.get("prompt") or "").strip()
        neg = (body.get("neg") or "").strip()
        if not prompt:
            return err("prompt 不能为空", "EMPTY_PROMPT", 400)

        # 兼容旧前端：普通生图也可携带 upscale/superres 直接走高清逻辑
        boost = bool(body.get("upscale", 1) > 1 or body.get("superres", False))
        upscale = body.get("upscale", DEFAULT_UPSCALE)
        superres = body.get("superres", True)
        seed = body.get("seed")

        img_url, size, params, mode = generate_image(
            prompt, neg, body.get("w", 512), body.get("h", 512),
            boost=boost, upscale=upscale, superres=superres, seed=seed,
        )
        return jsonify(ok=True, img_url=img_url, mode=mode,
                       size=size, params=params)
    except Exception as e:  # noqa: BLE001
        return err(str(e))


@app.route("/api/boost", methods=["POST"])
def boost():
    """Boost HD 高清增强专用接口：接收 upscale / superres / seed。"""
    try:
        body = request.get_json(force=True, silent=True) or {}
        prompt = (body.get("prompt") or "").strip()
        neg = (body.get("neg") or "").strip()
        if not prompt:
            return err("prompt 不能为空", "EMPTY_PROMPT", 400)

        upscale = body.get("upscale", DEFAULT_UPSCALE)
        superres = body.get("superres", True)
        seed = body.get("seed")

        img_url, size, params, mode = generate_image(
            prompt, neg, body.get("w", 512), body.get("h", 512),
            boost=True, upscale=upscale, superres=superres, seed=seed,
        )
        return jsonify(ok=True, img_url=img_url, mode=mode,
                       size=size, params=params)
    except Exception as e:  # noqa: BLE001
        return err(str(e))


@app.route("/api/proxy_image")
def proxy_image():
    """CORS 安全的图片下载代理：后端拉取图片后回传，规避浏览器跨域限制。"""
    url = request.args.get("url")
    if not url or not url.startswith("http"):
        return err("invalid url", "BAD_URL", 400)
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return err(f"代理拉取失败: {e}", "PROXY_FAILED", 502)
    ct = r.headers.get("Content-Type", "image/png")
    return Response(
        r.content,
        mimetype=ct,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store",
            "Content-Disposition": "attachment",
        },
    )


@app.route("/api/demo")
def demo_image():
    prompt = unquote(request.args.get("prompt", "SeaArt AI Demo"))
    hd = request.args.get("hd", "0") in ("1", "true", "True")
    svg = build_demo_svg(prompt, hd=hd)
    return Response(
        svg,
        mimetype="image/svg+xml",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if not path:
        path = "index.html"
    file_path = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    # 监听地址与端口可通过环境变量覆盖，便于域名/反向代理部署：
    #   HOST=0.0.0.0 (默认，监听所有网卡)   PORT=5000 (默认)
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "5000"))
    print(f"[SeaArt] DRAW_BACKEND={DRAW_BACKEND}  DEMO_MODE={DEMO_MODE}")
    print(f"[SeaArt] active model={_active_model()}  "
          f"(key {'set' if not DEMO_MODE else 'NOT set'})")
    print(f"[SeaArt] Zhipu={LLM_MODEL}@{LLM_BASE_URL}")
    print(f"[SeaArt] Agnes={AGNES_MODEL}@{AGNES_BASE_URL}")
    print(f"[SeaArt] serving frontend from {FRONTEND_DIR}")
    print(f"[SeaArt] running on http://{HOST}:{PORT}  (CORS enabled, 0.0.0.0 适配域名部署)")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)

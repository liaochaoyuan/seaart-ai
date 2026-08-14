// SeaArt AI - Cloudflare Pages Functions 共享工具
// 将原 Python Flask 后端的生图逻辑移植到 JavaScript，运行在 Cloudflare Edge。

const DEFAULT_UPSCALE = 2;
const MIN_UPSCALE = 1;
const MAX_UPSCALE = 4;

export function clampDim(v, lo = 512, hi = 2048) {
  try {
    v = parseInt(v, 10);
  } catch {
    v = 512;
  }
  if (Number.isNaN(v)) v = 512;
  v = Math.max(lo, Math.min(hi, v));
  return Math.max(lo, Math.floor(v / 8) * 8);
}

export function mapSize(w, h, backend = "zhipu", hd = false) {
  try {
    w = parseInt(w, 10) || 1024;
    h = parseInt(h, 10) || 1024;
  } catch {
    return "1024x1024";
  }
  const ar = h ? (w / h) : 1.0;
  if (backend === "agnes") {
    if (ar >= 0.8 && ar <= 1.25) return "1024x1024";
    if (ar > 1.25) return "1024x768";
    return "768x1024";
  }
  // zhipu
  if (ar >= 0.8 && ar <= 1.25) return "1024x1024";
  if (ar > 1.25) return "1440x720";
  return "720x1440";
}

export function hdEnhance(prompt, neg, superres) {
  if (!superres) return [prompt, neg];
  const hdPos = "，超高清，8k分辨率，极致细节，超分辨率重建，锐利清晰，高保真";
  const hdNeg = "，模糊，低分辨率，锯齿，压缩伪影，涂抹感";
  return [prompt + hdPos, neg + hdNeg];
}

export function buildDemoSvg(prompt, hd = false) {
  const safe = (prompt || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const tag = hd ? "SeaArt Demo HD" : "SeaArt Demo";
  const note = hd
    ? "演示模式示例图 (HD)"
    : "未配置密钥 / 接口异常 / 误用文本模型 — 演示示例图";
  return (
    '<svg xmlns="http://www.w3.org/2000/svg" width="768" height="768">' +
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
    '<stop offset="0%" stop-color="#a78bfa"/>' +
    '<stop offset="100%" stop-color="#ffd066"/></linearGradient></defs>' +
    '<rect width="768" height="768" fill="url(#g)"/>' +
    '<text x="384" y="360" font-size="34" fill="#0c0c12" text-anchor="middle" ' +
    'font-family="sans-serif" font-weight="bold">' + tag + '</text>' +
    '<text x="384" y="410" font-size="20" fill="#1a1a2e" text-anchor="middle" ' +
    'font-family="sans-serif">' + safe.slice(0, 40) + '</text>' +
    '<text x="384" y="700" font-size="14" fill="#1a1a2e" text-anchor="middle" ' +
    'font-family="sans-serif">' + note + '</text>' +
    '</svg>'
  );
}

export function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

export function errorResponse(msg, code = "GEN_FAILED", status = 500) {
  return jsonResponse({ ok: false, msg, code }, status);
}

export function getConfig(env) {
  const drawBackend = (env.DRAW_BACKEND || "zhipu").toLowerCase();
  const activeKey = drawBackend === "agnes"
    ? (env.AGNES_API_KEY || "")
    : (env.LLM_API_KEY || "");
  return {
    DRAW_BACKEND: drawBackend,
    LLM_API_KEY: env.LLM_API_KEY || "",
    LLM_BASE_URL: env.LLM_BASE_URL || "https://open.bigmodel.cn/api/paas/v4/",
    LLM_MODEL: env.LLM_MODEL || "cogview-3-flash",
    AGNES_API_KEY: env.AGNES_API_KEY || "",
    AGNES_BASE_URL: env.AGNES_BASE_URL || "https://apihub.agnes-ai.com/v1",
    AGNES_MODEL: env.AGNES_MODEL || "agnes-image-2.0-flash",
    DEMO_MODE: !activeKey,
  };
}

export function activeModel(config) {
  return config.DRAW_BACKEND === "agnes" ? config.AGNES_MODEL : config.LLM_MODEL;
}

export function demoImgUrl(request, prompt) {
  const url = new URL(request.url);
  return url.origin + "/api/demo?hd=1&prompt=" + encodeURIComponent((prompt || "").slice(0, 60));
}

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timer);
    return resp;
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}

export async function postZhipu(config, prompt, neg, w, h, seed = null, hd = false) {
  const size = mapSize(w, h, "zhipu", hd);
  let genPrompt = prompt;
  if (neg) genPrompt = prompt + "（避免：" + neg + "）";

  const url = config.LLM_BASE_URL.replace(/\/$/, "") + "/images/generations";
  const payload = {
    model: config.LLM_MODEL,
    prompt: genPrompt,
    size,
    n: 1,
  };
  if (neg) payload.negative_prompt = neg;
  if (seed !== null && seed !== undefined) payload.seed = parseInt(seed, 10);

  const resp = await fetchWithTimeout(
    url,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + config.LLM_API_KEY,
      },
      body: JSON.stringify(payload),
    },
    30000
  );

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error("Zhipu HTTP " + resp.status + ": " + text.slice(0, 200));
  }
  const d = await resp.json();
  const data = d.data || [];
  if (data.length && (data[0].url || data[0].b64_json)) {
    return data[0].url || data[0].b64_json;
  }
  throw new Error("智谱返回中未包含图片地址");
}

export async function postAgnes(config, prompt, neg, w, h, seed = null, hd = false) {
  const size = mapSize(w, h, "agnes", hd);
  let genPrompt = prompt;
  if (neg) genPrompt = prompt + "（避免：" + neg + "）";

  const url = config.AGNES_BASE_URL.replace(/\/$/, "") + "/images/generations";
  let payload = {
    model: config.AGNES_MODEL,
    prompt: genPrompt,
    size,
    n: 1,
  };
  if (neg) payload.negative_prompt = neg;
  if (seed !== null && seed !== undefined) payload.seed = parseInt(seed, 10);

  const headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + config.AGNES_API_KEY,
  };

  let lastErr = "Agnes 调用失败";
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const resp = await fetchWithTimeout(
        url,
        { method: "POST", headers, body: JSON.stringify(payload) },
        30000
      );

      const bodyText = await resp.text();
      let body = {};
      try { body = JSON.parse(bodyText); } catch {}

      if (resp.status === 200) {
        const data = body.data || [];
        if (data.length && (data[0].url || data[0].b64_json)) {
          return data[0].url || data[0].b64_json;
        }
        throw new Error(
          body.msg || body.error || body.message || "Agnes 返回中未包含图片地址"
        );
      }

      const errObj = body.error || {};
      const msg = errObj.message || body.message || body.error || bodyText;
      const dropped = [...msg.matchAll(/Setting `(\w+)` is not supported/g)].map(m => m[1]);
      if (dropped.length && dropped.some(k => payload[k] !== undefined)) {
        for (const k of dropped) delete payload[k];
        lastErr = msg;
        continue;
      }
      throw new Error(msg.slice(0, 300));
    } catch (e) {
      if (e.name === "AbortError" || (e.message && e.message.includes("timed out"))) {
        lastErr = "Agnes 请求超时";
        continue;
      }
      throw e;
    }
  }
  throw new Error(lastErr.slice(0, 300));
}

export async function postDraw(config, prompt, neg, w, h, seed = null, hd = false) {
  if (config.DRAW_BACKEND === "agnes") {
    return postAgnes(config, prompt, neg, w, h, seed, hd);
  }
  return postZhipu(config, prompt, neg, w, h, seed, hd);
}

export async function generateImage(config, request, prompt, neg, w, h, boost = false, upscale = 2, superres = true, seed = null) {
  upscale = Math.max(MIN_UPSCALE, Math.min(MAX_UPSCALE, parseInt(upscale || DEFAULT_UPSCALE, 10) || DEFAULT_UPSCALE));
  let width, height;
  if (boost) {
    [prompt, neg] = hdEnhance(prompt, neg, superres);
    width = clampDim(parseInt(w, 10) * upscale);
    height = clampDim(parseInt(h, 10) * upscale);
  } else {
    width = clampDim(w);
    height = clampDim(h);
  }

  const meta = { upscale, superres };

  if (config.DEMO_MODE) {
    return {
      imgUrl: demoImgUrl(request, prompt),
      size: { w: width, h: height },
      params: meta,
      mode: "demo",
    };
  }

  try {
    const imgUrl = await postDraw(config, prompt, neg, width, height, seed, boost);
    return {
      imgUrl,
      size: { w: width, h: height },
      params: meta,
      mode: config.DRAW_BACKEND,
    };
  } catch (e) {
    return {
      imgUrl: demoImgUrl(request, prompt),
      size: { w: width, h: height },
      params: { ...meta, fallback: true, reason: String(e).slice(0, 200) },
      mode: "demo",
    };
  }
}

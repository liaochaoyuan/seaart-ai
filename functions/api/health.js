import { jsonResponse, getConfig, activeModel } from "../_shared/utils.js";

export async function onRequest(context) {
  const config = getConfig(context.env);
  return jsonResponse({
    ok: true,
    backend: config.DRAW_BACKEND,
    mode: config.DEMO_MODE ? "demo" : config.DRAW_BACKEND,
    demo: config.DEMO_MODE,
    model: activeModel(config),
    msg: config.DEMO_MODE
      ? `demo mode (no API key for ${config.DRAW_BACKEND})`
      : `${config.DRAW_BACKEND} ready`,
  });
}

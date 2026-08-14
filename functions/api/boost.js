import { jsonResponse, errorResponse, generateImage } from "../_shared/utils.js";

export async function onRequestPost(context) {
  try {
    const config = getConfig(context.env);
    const body = await context.request.json().catch(() => ({}));

    const prompt = (body.prompt || "").trim();
    const neg = (body.neg || "").trim();
    if (!prompt) {
      return errorResponse("prompt 不能为空", "EMPTY_PROMPT", 400);
    }

    const upscale = body.upscale || 2;
    const superres = body.superres !== false;
    const seed = body.seed;

    const result = await generateImage(
      config,
      context.request,
      prompt,
      neg,
      body.w || 512,
      body.h || 512,
      true,
      upscale,
      superres,
      seed
    );

    return jsonResponse({
      ok: true,
      img_url: result.imgUrl,
      mode: result.mode,
      size: result.size,
      params: result.params,
    });
  } catch (e) {
    return errorResponse(String(e));
  }
}

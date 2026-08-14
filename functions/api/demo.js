import { buildDemoSvg } from "../_shared/utils.js";

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const prompt = decodeURIComponent(url.searchParams.get("prompt") || "SeaArt AI Demo");
  const hd = ["1", "true", "True"].includes(url.searchParams.get("hd") || "0");
  const svg = buildDemoSvg(prompt, hd);
  return new Response(svg, {
    status: 200,
    headers: {
      "Content-Type": "image/svg+xml",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

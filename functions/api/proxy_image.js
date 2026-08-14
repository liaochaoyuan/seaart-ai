export async function onRequest(context) {
  const url = new URL(context.request.url).searchParams.get("url");
  if (!url || !url.startsWith("http")) {
    return new Response(JSON.stringify({ ok: false, msg: "invalid url", code: "BAD_URL" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    const r = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);

    if (!r.ok) throw new Error("HTTP " + r.status);
    const blob = await r.blob();
    return new Response(blob, {
      status: 200,
      headers: {
        "Content-Type": r.headers.get("Content-Type") || "image/png",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-store",
        "Content-Disposition": "attachment",
      },
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ ok: false, msg: "代理拉取失败: " + String(e), code: "PROXY_FAILED" }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}

/**
 * NFL_stats "Ask" Worker — a locked-down pass-through to the Claude API for the Lab's Ask box.
 * The instructions and answer parsing live in lab.html, so prompt changes never need a redeploy.
 *
 * Secrets (Settings → Variables and Secrets):
 *   ANTHROPIC_API_KEY  your key from the Claude Console
 *   PASSCODE           the phrase you type into the Lab once
 * Optional plain variables:
 *   MODEL              defaults to claude-haiku-5-5
 *   ALLOWED_ORIGINS    defaults to https://william-arana.github.io
 *
 * Guards: only your site's origin, only with the passcode, capped prompt size and answer length.
 */
export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const allowed = (env.ALLOWED_ORIGINS || "https://william-arana.github.io").split(",").map((s) => s.trim());
    const cors = {
      "Access-Control-Allow-Origin": allowed.includes(origin) ? origin : allowed[0],
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, X-Passcode",
      "Vary": "Origin",
    };
    const reply = (obj, status = 200) =>
      new Response(JSON.stringify(obj), { status, headers: { ...cors, "Content-Type": "application/json" } });

    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "POST") return reply({ error: "Use POST" }, 405);
    if (!allowed.includes(origin)) return reply({ error: "This site isn't allowed to use the Ask box." }, 403);
    if (!env.PASSCODE || request.headers.get("X-Passcode") !== env.PASSCODE) return reply({ error: "Wrong passcode." }, 401);
    if (!env.ANTHROPIC_API_KEY) return reply({ error: "The Worker is missing ANTHROPIC_API_KEY." }, 500);

    let body;
    try { body = await request.json(); } catch { return reply({ error: "Bad request body." }, 400); }
    const system = String(body.system || "").slice(0, 24000);
    const question = String(body.question || "").trim().slice(0, 4000);
    if (!question) return reply({ error: "Type a question first." }, 400);
    if (!system) return reply({ error: "This page is out of date. Hard-refresh the Lab and try again." }, 400);

    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({
        model: env.MODEL || "claude-haiku-5-5",
        max_tokens: 1500,
        system,
        messages: [{ role: "user", content: question }],
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return reply({ error: (data.error && data.error.message) || `Claude API error ${r.status}` }, 502);
    const text = (data.content || []).filter((c) => c.type === "text").map((c) => c.text).join("");
    return reply({ text, usage: data.usage || null, model: data.model || null });
  },
};

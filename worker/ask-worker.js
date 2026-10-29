/**
 * NFL_stats "Ask" Worker — turns a plain-English question into DuckDB SQL for the Lab.
 *
 * Paste this whole file into a Cloudflare Worker. It needs two secrets (Settings → Variables and Secrets):
 *   ANTHROPIC_API_KEY  your key from the Claude Console
 *   PASSCODE           any phrase you make up; you type it into the Lab once
 * Optional plain variables:
 *   MODEL              defaults to claude-haiku-5-5
 *   ALLOWED_ORIGINS    defaults to https://william-arana.github.io
 *
 * The Worker only answers requests from your site that carry the passcode, only writes SQL
 * (it never runs anything), and caps each answer's length, so a leaked URL can't run up a bill.
 */
const RULES = `You write one DuckDB SQL query for a fantasy football analysis page.
Return ONLY a JSON object, no prose around it: {"sql": "...", "explanation": "one or two plain sentences on what the query does and any assumption you made"}.
Rules:
- Read-only: a single SELECT (CTEs allowed). Never CREATE, INSERT, UPDATE, DELETE, ATTACH, COPY, PRAGMA, INSTALL or LOAD.
- Use only the tables and columns listed in the schema. Do not invent columns.
- "Available", "free agent", "on waivers" = avail.status = 'fa'. "My team"/"my players" = avail.status = 'mine'.
- "This week"/"next game"/"matchup" = games_long where week = (SELECT next_week FROM meta). games_long has one row per team: team, opp, implied (team's Vegas implied points), opp_implied.
- Matchup strength for a player = fantasy points per game the opponent defense allows to that position, from players grouped by opponent_team and position. Turn it into a z-score with window functions when ranking.
- Recent form = last 3 weeks: week > (SELECT last_completed_week FROM meta) - 3.
- Default fantasy scoring is PPR (fantasy_points_ppr). xfp = expected PPR points from usage.
- offense_pct and target_share are fractions (0.62 = 62%); multiply by 100 when showing percents.
- Team codes are NFL abbreviations (LV = Raiders, KC = Chiefs, LA = Rams, LAC = Chargers, NYJ, NYG, JAX, WAS, etc.).
- Round decimals to 1–2 places, give columns readable snake_case names, put the player or team name first, ORDER BY the most useful column, LIMIT 50 unless asked otherwise.`;

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
    const question = String(body.question || "").trim().slice(0, 600);
    const schema = String(body.schema || "").slice(0, 15000);
    const context = String(body.context || "").slice(0, 2000);
    if (!question) return reply({ error: "Type a question first." }, 400);

    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: env.MODEL || "claude-haiku-5-5",
        max_tokens: 1500,
        system: `${RULES}\n\nSCHEMA (table: columns with types)\n${schema}\n\nCONTEXT\n${context}`,
        messages: [{ role: "user", content: question }],
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return reply({ error: (data.error && data.error.message) || `Claude API error ${r.status}` }, 502);

    const text = (data.content || []).filter((c) => c.type === "text").map((c) => c.text).join("");
    const m = text.match(/\{[\s\S]*\}/);
    let out;
    try { out = JSON.parse(m ? m[0] : text); } catch { return reply({ error: "Couldn't read Claude's answer. Try rewording.", raw: text.slice(0, 500) }, 502); }
    if (!out.sql || !/^\s*(with|select)\b/i.test(out.sql) || /\b(create|insert|update|delete|attach|copy|pragma|install|load|drop|alter)\b/i.test(out.sql))
      return reply({ error: "Claude returned something other than a read-only query. Try rewording.", sql: out.sql || "" }, 422);
    return reply({ sql: out.sql.trim(), explanation: out.explanation || "", usage: data.usage || null });
  },
};

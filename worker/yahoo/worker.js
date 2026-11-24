/**
 * GameDay_stats private Yahoo Worker ("My Yahoo team"), only for William.
 *
 * Behind Cloudflare Access (policy "William only"), and it also checks the Access login token itself.
 * Design rules:
 *   - only William's own team in his own league; read-only
 *   - fetched live on every request, `Cache-Control: no-store`, nothing from Yahoo is saved
 *     (KV holds only the Yahoo sign-in, encrypted)
 *   - no other team's roster; standings/matchup = names, records, points
 *   - this Worker has no Claude key and never calls an AI service
 *   - "Fantasy data provided by Yahoo Fantasy" + link on the page
 *
 * Routes:  /            the page (me.html)
 *          /connect     one-time Yahoo sign-in (paste the code Yahoo gives you)
 *          /api/team    my roster for the current week + my matchup + standings
 *          /api/fa?pos= available players (free agents + waivers) at one position
 *
 * Secrets (set by the deploy workflow): YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET.
 * Vars (wrangler.jsonc): ACCESS_TEAM, ACCESS_AUD, YAHOO_LEAGUE_ID, SITE. KV binding: YAHOO_KV.
 */
import PAGE from "./me.html";

const API = "https://fantasysports.yahooapis.com/fantasy/v2";
const AUTH = "https://api.login.yahoo.com/oauth2";
const REDIRECT = "https://localhost:8080"; // FFB26c's redirect URI (Yahoo shows the code in that address)
const KV_KEY = "yahoo-signin:william";
const POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"];
const TEAM_FIX = { LAR: "LA", JAC: "JAX", WSH: "WAS" };

const NOSTORE = { "Cache-Control": "no-store", "X-Robots-Tag": "noindex" };
const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { ...NOSTORE, "Content-Type": "application/json" } });
const html = (body, status = 200) =>
  new Response(body, { status, headers: { ...NOSTORE, "Content-Type": "text/html; charset=utf-8" } });

export default {
  async fetch(request, env) {
    const who = await checkAccess(request, env);
    if (!who) return new Response("Sign in through Cloudflare Access first.", { status: 403, headers: NOSTORE });

    const url = new URL(request.url);
    try {
      if (url.pathname === "/" || url.pathname === "/me") return html(await page(env));
      if (url.pathname === "/connect") return request.method === "POST" ? await connect(request, env) : html(connectPage(env));
      if (url.pathname === "/api/team") return json(await team(env));
      if (url.pathname === "/api/fa") return json(await freeAgents(env, (url.searchParams.get("pos") || "").toUpperCase()));
      return json({ error: "Not found" }, 404);
    } catch (e) {
      const msg = String((e && e.message) || e);
      if (msg === "NOT_CONNECTED") return json({ error: "not_connected" }, 409);
      if (/\b403\b/.test(msg)) return json({ error: "yahoo_403", detail: "Yahoo said this app isn't authorized (403)." }, 502);
      return json({ error: "failed", detail: msg.slice(0, 300) }, 502);
    }
  },
};

/* ---------- Cloudflare Access: verify the signed login token on every request ---------- */
let CERTS = null;
async function checkAccess(request, env) {
  const jwt = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!jwt || !env.ACCESS_TEAM || !env.ACCESS_AUD) return null;
  try {
    const [h, p, s] = jwt.split(".");
    const head = JSON.parse(b64urlText(h));
    const claims = JSON.parse(b64urlText(p));
    const iss = `https://${env.ACCESS_TEAM}.cloudflareaccess.com`;
    const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    if (claims.iss !== iss || !aud.includes(env.ACCESS_AUD) || !(claims.exp > Date.now() / 1000)) return null;
    if (!CERTS || !CERTS.keys.some((k) => k.kid === head.kid)) CERTS = await (await fetch(`${iss}/cdn-cgi/access/certs`)).json();
    const jwk = CERTS.keys.find((k) => k.kid === head.kid);
    if (!jwk) return null;
    const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64urlBytes(s), new TextEncoder().encode(`${h}.${p}`));
    return ok ? claims.email || "ok" : null;
  } catch {
    return null;
  }
}
function b64urlBytes(s) {
  const b = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}
const b64urlText = (s) => new TextDecoder().decode(b64urlBytes(s));

/* ---------- the page ---------- */
async function page(env) {
  let v = "";
  try {
    v = (await (await fetch(`${env.SITE}/version.json`, { cf: { cacheTtl: 300 } })).json()).version || "";
  } catch {}
  return PAGE.replaceAll("{{SITE}}", env.SITE).replaceAll("{{V}}", v);
}

/* ---------- Yahoo sign-in, kept encrypted in KV (the sign-in is the only thing stored) ---------- */
async function kvKey(env) {
  const raw = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${env.YAHOO_CLIENT_SECRET}:gameday-yahoo-kv`));
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}
async function saveSignin(env, tok) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const data = new TextEncoder().encode(JSON.stringify(tok));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await kvKey(env), data));
  await env.YAHOO_KV.put(KV_KEY, btoa(String.fromCharCode(...iv, ...ct)));
}
async function loadSignin(env) {
  const s = await env.YAHOO_KV.get(KV_KEY);
  if (!s) return null;
  const b = Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b.slice(0, 12) }, await kvKey(env), b.slice(12));
  return JSON.parse(new TextDecoder().decode(pt));
}
async function tokenRequest(env, params) {
  const r = await fetch(`${AUTH}/get_token`, {
    method: "POST",
    headers: {
      Authorization: "Basic " + btoa(`${env.YAHOO_CLIENT_ID}:${env.YAHOO_CLIENT_SECRET}`),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ ...params, redirect_uri: REDIRECT }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || !j.access_token) throw new Error(`Yahoo sign-in failed (${r.status}): ${j.error_description || j.error || ""}`);
  return j;
}
async function accessToken(env) {
  const s = await loadSignin(env);
  if (!s || !s.refresh_token) throw new Error("NOT_CONNECTED");
  if (s.access_token && s.expires_at > Date.now() + 60_000) return s.access_token;
  const t = await tokenRequest(env, { grant_type: "refresh_token", refresh_token: s.refresh_token });
  await saveSignin(env, {
    refresh_token: t.refresh_token || s.refresh_token,
    access_token: t.access_token,
    expires_at: Date.now() + (t.expires_in || 3600) * 1000,
  });
  return t.access_token;
}

function connectPage(env, msg = "") {
  const link = `${AUTH}/request_auth?` + new URLSearchParams({ client_id: env.YAHOO_CLIENT_ID || "", redirect_uri: REDIRECT, response_type: "code" });
  return `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Connect Yahoo</title>
<style>body{font:15px/1.5 system-ui,sans-serif;max-width:560px;margin:40px auto;padding:0 16px;color:#16213a;background:#fbfcfe}
a.btn,button{display:inline-block;background:#1d4fd8;color:#fff;border:0;border-radius:6px;padding:10px 14px;font:inherit;text-decoration:none;cursor:pointer}
input{width:100%;font:inherit;padding:10px;border:1px solid #dfe6f2;border-radius:6px;margin:8px 0}.msg{padding:10px;border-radius:6px;background:#e6edfd}</style>
<h1>Connect Yahoo</h1>${msg ? `<p class="msg">${msg}</p>` : ""}
<p>1. Open Yahoo and click <b>Agree</b>. It then goes to a <code>localhost</code> address that won't load. That's expected.</p>
<p><a class="btn" href="${link}" target="_blank" rel="noopener">Open Yahoo</a></p>
<p>2. Copy that whole address (or just the code) and paste it here. The code expires in about 10 minutes.</p>
<form method="post"><input name="code" autocomplete="off" placeholder="https://localhost:8080/?code=…" required><button>Connect</button></form>
<p><a href="/">← My Yahoo team</a></p>`;
}
async function connect(request, env) {
  const f = await request.formData();
  let code = String(f.get("code") || "").trim();
  if (code.includes("code=")) code = code.split("code=")[1].split("&")[0];
  if (!code) return html(connectPage(env, "Paste the code first."), 400);
  try {
    const t = await tokenRequest(env, { grant_type: "authorization_code", code });
    await saveSignin(env, { refresh_token: t.refresh_token, access_token: t.access_token, expires_at: Date.now() + (t.expires_in || 3600) * 1000 });
  } catch (e) {
    return html(connectPage(env, String(e.message || e)), 400);
  }
  return new Response(null, { status: 303, headers: { ...NOSTORE, Location: "/" } });
}

/* ---------- Yahoo API ---------- */
async function y(env, path) {
  const r = await fetch(`${API}/${path}${path.includes("?") ? "&" : "?"}format=json`, {
    headers: { Authorization: "Bearer " + (await accessToken(env)) },
    cf: { cacheTtl: 0, cacheEverything: false },
  });
  if (!r.ok) throw new Error(`${r.status} on ${path.split("/")[0]}: ${(await r.text()).slice(0, 200)}`);
  return (await r.json()).fantasy_content;
}
// Yahoo's JSON: objects come as lists of one-key dicts, collections as {"0": {...}, "1": {...}, "count": n}
function merge(x) {
  if (x && !Array.isArray(x) && typeof x === "object") return x;
  const out = {};
  for (const it of x || []) {
    if (Array.isArray(it)) Object.assign(out, merge(it));
    else if (it && typeof it === "object") Object.assign(out, it);
  }
  return out;
}
const items = (coll, key) =>
  coll && typeof coll === "object" ? Object.entries(coll).filter(([k, v]) => k !== "count" && v && v[key]).map(([, v]) => v[key]) : [];

function player(p) {
  const m = merge(Array.isArray(p) ? p[0] : p);
  const extra = Array.isArray(p) ? merge(p.slice(1)) : {};
  const pos = m.display_position || m.primary_position || "";
  const abbr = String(m.editorial_team_abbr || "").toUpperCase();
  const sel = merge(extra.selected_position || []);
  return {
    yid: String(m.player_id || ""),
    name: (m.name && m.name.full) || "",
    pos,
    elig: (Array.isArray(m.eligible_positions) ? m.eligible_positions : Object.values(m.eligible_positions || {}))
      .map((e) => e && e.position)
      .filter(Boolean),
    team: TEAM_FIX[abbr] || abbr,
    status: m.status || "",
    bye: Number((m.bye_weeks && m.bye_weeks.week) || 0) || null,
    slot: sel.position || null,
  };
}

let GAME = null;
async function myTeamKey(env) {
  if (!GAME) GAME = String(merge((await y(env, "game/nfl")).game).game_key);
  const lk = `${GAME}.l.${env.YAHOO_LEAGUE_ID}`;
  const u = merge(items((await y(env, `users;use_login=1/games;game_keys=${GAME}/teams`)).users, "user")[0]);
  for (const g of items(u.games || {}, "game")) {
    for (const t of items(merge(g).teams || {}, "team")) {
      const tm = merge(Array.isArray(t) && Array.isArray(t[0]) ? t[0] : t);
      if (String(tm.team_key || "").startsWith(lk + ".t.")) return { lk, tk: tm.team_key, name: tm.name };
    }
  }
  throw new Error(`Couldn't find your team in league ${env.YAHOO_LEAGUE_ID}`);
}

async function team(env) {
  const me = await myTeamKey(env);
  const lg = merge((await y(env, `league/${me.lk}`)).league);
  const week = Number(lg.current_week || 1);
  const rosterT = (await y(env, `team/${me.tk}/roster;week=${week}`)).team;
  const roster = merge(rosterT.slice ? rosterT.slice(1) : []).roster || {};
  const players = items((roster["0"] || {}).players || {}, "player").map(player);

  // my matchup: my points vs my opponent's (names + points only, no opponent roster)
  let matchup = null;
  try {
    const mt = (await y(env, `team/${me.tk}/matchups;weeks=${week}`)).team;
    const ms = items(merge(mt.slice ? mt.slice(1) : []).matchups || {}, "matchup")[0];
    if (ms) {
      const sides = items((ms["0"] || {}).teams || {}, "team").map((t) => {
        const a = merge(t[0] || []);
        const b = merge(t.slice ? t.slice(1) : []);
        return {
          name: a.name,
          mine: a.team_key === me.tk,
          points: Number((b.team_points || {}).total || 0),
          projected: Number((b.team_projected_points || {}).total || 0),
          win_probability: b.win_probability != null ? Number(b.win_probability) : null,
        };
      });
      matchup = { week, status: ms.status || "", sides };
    }
  } catch {}

  // standings: name, record, points for/against only
  let standings = [];
  try {
    const st = merge((await y(env, `league/${me.lk}/standings`)).league).standings;
    const coll = ((Array.isArray(st) ? st[0] : st) || {}).teams || {};
    standings = items(coll, "team").map((t) => {
      const a = merge(t[0] || []);
      const b = merge(t.slice ? t.slice(1) : []);
      const ts = b.team_standings || {};
      const ot = ts.outcome_totals || {};
      return {
        name: a.name,
        mine: a.team_key === me.tk,
        rank: Number(ts.rank || 0) || null,
        w: Number(ot.wins || 0), l: Number(ot.losses || 0), t: Number(ot.ties || 0),
        pf: Number(ts.points_for || 0), pa: Number(ts.points_against || 0),
      };
    });
  } catch {}

  return { league: lg.name, league_url: lg.url, team: me.name, week, players, matchup, standings, fetched_utc: new Date().toISOString() };
}

async function freeAgents(env, pos) {
  if (!POSITIONS.includes(pos)) return { error: "Pick a position: " + POSITIONS.join(", ") };
  const me = await myTeamKey(env);
  // status=A = available (free agents + waivers); AR = Yahoo's actual-rank sort; 25 is the per-call max
  const lgp = (await y(env, `league/${me.lk}/players;status=A;position=${pos};sort=AR;count=25`)).league;
  const players = items(merge(lgp.slice ? lgp.slice(1) : []).players || {}, "player").map(player);
  return { pos, players, fetched_utc: new Date().toISOString() };
}

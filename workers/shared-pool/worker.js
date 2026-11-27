// SharkyClips shared-pool counter (1.2.75, prepared; not deployed until Google verifies the client).
//
// A free Cloudflare Worker that tells the app how much of the built-in Google client's daily
// YouTube upload pool is used today:  GET /  ->  {"used": 50, "limit": 100, "resets_at": "...Z"}
//
// It reads Google Cloud Monitoring (the project's own quota metrics) with a READ-ONLY service
// account (role "Monitoring Viewer"). The service-account key lives only in the Worker secret
// SA_KEY (wrangler secret put SA_KEY), never in the repository. Requests carry no user data; the
// Worker keeps no logs of its own and answers from a 5-minute cache. Setup: docs/phase-d5.md.
//
// Variables (wrangler.toml [vars]):
//   PROJECT_ID    the Google Cloud project of the built-in client
//   QUOTA_METRIC  the quota metric of the upload bucket, as Cloud Console > IAM & Admin > Quotas
//                 shows it for "YouTube Data API v3" (e.g. youtube.googleapis.com/...)
//   LIMIT         optional: the daily limit when the limit metric can't be read (default 100)

const MONITORING = "https://monitoring.googleapis.com/v3/projects";
const TOKEN_URL = "https://oauth2.googleapis.com/token";
const SCOPE = "https://www.googleapis.com/auth/monitoring.read";
const CACHE_S = 300;

/** Midnight Pacific Time that started the current quota day, and the next one (Date, UTC). */
export function pacificDay(now = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles", hourCycle: "h23",
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
    }).formatToParts(now).map((p) => [p.type, p.value]),
  );
  const wall = Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour, +parts.minute, +parts.second);
  const offset = wall - Math.floor(now.getTime() / 1000) * 1000; // Pacific minus UTC (negative)
  // midnight of that Pacific date (the offset of "now" may differ from midnight's on a DST day)
  const start = toMidnight(new Date(Date.UTC(+parts.year, +parts.month - 1, +parts.day) - offset));
  // the next midnight: 24 h later, corrected when DST changes in between
  return { start, next: toMidnight(new Date(start.getTime() + 24 * 3600 * 1000)) };
}

/** A time within an hour of a Pacific midnight, moved onto it (DST: 23 h and 25 h days). */
function toMidnight(d) {
  const h = +new Intl.DateTimeFormat("en-US", { timeZone: "America/Los_Angeles", hourCycle: "h23", hour: "2-digit" })
    .formatToParts(d).find((p) => p.type === "hour").value;
  return new Date(d.getTime() + (h === 0 ? 0 : h === 23 ? 3600 * 1000 : -3600 * 1000));
}

function b64url(bytes) {
  let s = "";
  for (const b of new Uint8Array(bytes)) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** A Google OAuth access token for the service account (JWT bearer grant, RS256). */
export async function accessToken(key, fetchFn = fetch, now = Date.now()) {
  const iat = Math.floor(now / 1000);
  const enc = new TextEncoder();
  const header = b64url(enc.encode(JSON.stringify({ alg: "RS256", typ: "JWT" })));
  const claims = b64url(enc.encode(JSON.stringify({ iss: key.client_email, scope: SCOPE, aud: TOKEN_URL, iat, exp: iat + 3600 })));
  const pem = String(key.private_key).replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const k = await crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", k, enc.encode(`${header}.${claims}`));
  const res = await fetchFn(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: `${header}.${claims}.${b64url(sig)}` }),
  });
  if (!res.ok) throw new Error(`token ${res.status}`);
  return (await res.json()).access_token;
}

/** The Monitoring query URL: one summed value over [start, end] for this quota metric. */
export function seriesUrl(project, metricType, quotaMetric, start, end, aligner) {
  const secs = Math.max(60, Math.ceil((end - start) / 1000));
  const filter = [
    `metric.type="${metricType}"`,
    `resource.type="consumer_quota"`,
    `resource.labels.service="youtube.googleapis.com"`,
    `metric.labels.quota_metric="${quotaMetric}"`,
  ].join(" AND ");
  const q = new URLSearchParams({
    filter,
    "interval.startTime": start.toISOString(),
    "interval.endTime": end.toISOString(),
    "aggregation.alignmentPeriod": `${secs}s`,
    "aggregation.perSeriesAligner": aligner,
    "aggregation.crossSeriesReducer": aligner === "ALIGN_SUM" ? "REDUCE_SUM" : "REDUCE_MAX",
  });
  return `${MONITORING}/${encodeURIComponent(project)}/timeSeries?${q}`;
}

function firstValue(data) {
  const v = data?.timeSeries?.[0]?.points?.[0]?.value;
  if (!v) return null;
  const n = Number(v.int64Value ?? v.doubleValue);
  return Number.isFinite(n) ? Math.round(n) : null;
}

/** {used, limit, resets_at} for today, straight from Cloud Monitoring. */
export async function readPool(env, fetchFn = fetch, now = new Date()) {
  if (!env.SA_KEY || !env.PROJECT_ID || !env.QUOTA_METRIC) throw new Error("not configured");
  const key = JSON.parse(env.SA_KEY);
  const token = await accessToken(key, fetchFn, now.getTime());
  const { start, next } = pacificDay(now);
  const get = async (url) => {
    const r = await fetchFn(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Error(`monitoring ${r.status}`);
    return r.json();
  };
  const used = firstValue(await get(seriesUrl(env.PROJECT_ID, "serviceruntime.googleapis.com/quota/rate/net_usage",
    env.QUOTA_METRIC, start, now, "ALIGN_SUM"))) ?? 0;
  // the limit metric is sampled about once a day: look back 2 days for its newest value
  const limit = firstValue(await get(seriesUrl(env.PROJECT_ID, "serviceruntime.googleapis.com/quota/limit",
    env.QUOTA_METRIC, new Date(now.getTime() - 2 * 86400 * 1000), now, "ALIGN_MAX"))) || Number(env.LIMIT) || 100;
  return { used: Math.max(0, used), limit, resets_at: next.toISOString().replace(/\.\d{3}Z$/, "Z") };
}

const json = (body, status = 200, maxAge = CACHE_S) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": `public, max-age=${maxAge}`, "X-Content-Type-Options": "nosniff" },
  });

export async function handle(request, env, ctx, deps = {}) {
  if (request.method !== "GET") return json({ error: "method" }, 405, 0);
  const url = new URL(request.url);
  if (url.pathname !== "/") return json({ error: "not found" }, 404, 0);
  const cache = deps.cache ?? (typeof caches !== "undefined" ? caches.default : null);
  const cacheKey = new Request(`${url.origin}/`, { method: "GET" }); // one entry, whatever was asked
  const hit = cache && (await cache.match(cacheKey));
  if (hit) return hit;
  let res;
  try {
    res = json(await readPool(env, deps.fetch ?? fetch, deps.now ?? new Date()));
  } catch {
    return json({ error: "unavailable" }, 503, 60);
  }
  if (cache) ctx?.waitUntil?.(cache.put(cacheKey, res.clone()));
  return res;
}

export default { fetch: (request, env, ctx) => handle(request, env, ctx) };

// 1.2.75 YouTube quota, honest:
//  - own Google client: an exact "X of Y uploads left today" (1 upload = 1 of Google's 100 a day)
//  - built-in (shared) client: "Shared daily pool, resets at <local time>" + my uploads today,
//    never a made-up count; the real pool number only when the pool counter is on
//  - quotaExceeded: "Today's shared upload limit is used up" + Upload manually / own client
//  - owner view (setting): a link to the Cloud Console quota page, nothing else
import { useEffect, useState } from "react";
import "../uploads.css";
import { useI18n } from "../i18n";
import { go, href } from "../router";
import { localTime, uploadsApi, type QuotaView } from "../uploads";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Toggle, revealById } from "./ui";

export function useQuotaView(): [QuotaView | null, (v: QuotaView) => void] {
  const [v, setV] = useState<QuotaView | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      uploadsApi
        .quota()
        .then((x) => alive && setV(x))
        .catch(() => {});
    load();
    const iv = window.setInterval(() => document.visibilityState === "visible" && load(), 60_000);
    window.addEventListener("sc-share-changed", load);
    return () => {
      alive = false;
      window.clearInterval(iv);
      window.removeEventListener("sc-share-changed", load);
    };
  }, []);
  return [v, setV];
}

function openOwnClient() {
  go(href.settings);
  window.setTimeout(() => revealById("youtube"), 350);
}

function Meter({ left, total, label }: { left: number; total: number; label: string }) {
  const pct = total > 0 ? Math.max(0, Math.min(100, (left / total) * 100)) : 0;
  return (
    <div className="yq-meter" role="meter" aria-valuemin={0} aria-valuemax={total} aria-valuenow={left} aria-label={label}>
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}

export function YouTubeQuota({ compact }: { compact?: boolean }) {
  const { t, lang, num } = useI18n();
  const [v] = useQuotaView();
  if (!v) return null;
  const q = v.quota;
  const time = localTime(v.resets_at, lang);
  const mine = q.mine_today ?? 0;
  const limit = q.uploads_limit ?? 100;
  const actions = (
    <div className="yq-actions">
      <button type="button" className="btn btn-sm" onClick={() => go(href.publish("list"))}>
        <Icon name="upload" size={13} /> {t("yq.upload_manually")}
      </button>
      {v.mode === "shared" && (
        <button type="button" className="btn btn-sm btn-ghost" onClick={openOwnClient}>
          <Icon name="settings" size={13} /> {t("yq.use_own")}
        </button>
      )}
    </div>
  );
  return (
    <div className={`yq${compact ? " is-compact" : ""}`} data-mode={v.mode ?? "none"}>
      {!compact && <h2 className="yq-title">{t("yq.title")}</h2>}
      {v.mode === null ? (
        <p className="muted yq-line">{t("yq.not_connected")}</p>
      ) : q.exhausted ? (
        <div className="notice notice-warn yq-exceeded" role="status">
          <Icon name="alert" />
          <div>
            <b>{v.mode === "shared" ? t("yq.exceeded_title") : t("yq.own_exceeded_title")}</b>
            <div>{t("yq.exceeded_body", { time })}</div>
            {actions}
          </div>
        </div>
      ) : v.mode === "own" ? (
        <>
          <div className="yq-big">
            <b className="mono">{t("yq.left_of", { n: num(q.uploads_left), total: num(limit) })}</b>
          </div>
          <Meter left={q.uploads_left} total={limit} label={t("yq.left_of", { n: num(q.uploads_left), total: num(limit) })} />
          <p className="muted yq-line">{t("yq.own_hint", { total: num(limit), cost: num(q.cost_per_upload ?? 1), time })}</p>
        </>
      ) : q.pool ? (
        <>
          <div className="yq-big">
            <b className="mono">{t("yq.pool_left", { n: num(q.pool.left), total: num(q.pool.limit) })}</b>
          </div>
          <Meter left={q.pool.left} total={q.pool.limit} label={t("yq.pool_left", { n: num(q.pool.left), total: num(q.pool.limit) })} />
          <p className="muted yq-line">
            {t("yq.pool_details", { used: num(q.pool.used), when: localTime(q.pool.fetched_at, lang), time })}
          </p>
          <p className="yq-line">{t("yq.mine_today", { n: num(mine) })}</p>
        </>
      ) : (
        <>
          <div className="yq-big">
            <b>{t("yq.shared_pool")}</b>
            <span className="chip chip-outline">{t("yq.resets", { time })}</span>
          </div>
          <p className="yq-line">{t("yq.mine_today", { n: num(mine) })}</p>
          <p className="muted yq-line">{t("yq.shared_pool_hint", { time })}</p>
        </>
      )}
      {v.mode === "own" && v.own_console_url && (
        <a className="yq-link" href={v.own_console_url} target="_blank" rel="noreferrer">
          <Icon name="link" size={12} /> {t("yq.own_console")}
        </a>
      )}
      {v.owner.console_url && (
        <a className="yq-link" href={v.owner.console_url} target="_blank" rel="noreferrer">
          <Icon name="chart" size={12} /> {t("yq.owner_link")}
        </a>
      )}
    </div>
  );
}

/** Settings > Advanced: the owner link and the (prepared, off) shared-pool counter. */
export function QuotaOwnerSettings() {
  const { t } = useI18n();
  const toast = useToast();
  const [v, setV] = useQuotaView();
  const [url, setUrl] = useState<string | null>(null);
  if (!v) return null;
  const save = (body: Parameters<typeof uploadsApi.saveQuotaSettings>[0]) =>
    uploadsApi
      .saveQuotaSettings(body)
      .then((x) => {
        setV(x);
        window.dispatchEvent(new Event("sc-share-changed"));
      })
      .catch((e: any) => toast({ kind: "err", text: e.message, hint: e.hint }));
  return (
    <section className="card setting" id="quota-owner">
      <div>
        <h2>{t("yq.owner_title")}</h2>
        <p>{t("yq.owner_hint")}</p>
      </div>
      <div className="yq-owner">
        <label className="yq-row">
          <Toggle checked={v.owner.enabled} onChange={(x) => save({ owner_view: x })} label={t("yq.owner_toggle")} />
          <span>{t("yq.owner_toggle")}</span>
        </label>
        <label className="yq-row">
          <Toggle checked={v.pool_counter.on} onChange={(x) => save({ pool_counter: x })} label={t("yq.pool_toggle")} />
          <span>{t("yq.pool_toggle")}</span>
        </label>
        <p className="field-hint">{t("yq.pool_toggle_hint")}</p>
        <div className="yq-url">
          <label className="field" style={{ flex: 1, minWidth: 0 }}>
            <span>{t("yq.pool_url")}</span>
            <input
              className="input mono"
              type="url"
              inputMode="url"
              placeholder="https://…workers.dev/"
              value={url ?? v.pool_counter.url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <button type="button" className="btn btn-sm" disabled={url === null} onClick={() => save({ pool_url: url ?? "" }).then(() => setUrl(null))}>
            {t("yq.save")}
          </button>
        </div>
      </div>
    </section>
  );
}

import { useCallback, useEffect, useId, useState } from "react";
import { ApiError, liveApi, type LiveView, type WatchPublish } from "../api";
import { useI18n } from "../i18n";
import { useMeta } from "../meta";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Segmented, Toggle } from "./ui";


/** The live/automation settings, loaded once and refreshed after each change. */
export function useLive() {
  const [live, setLive] = useState<LiveView | null>(null);
  const toast = useToast();
  const reload = useCallback(() => liveApi.get().then(setLive).catch(() => {}), []);
  useEffect(() => {
    reload();
  }, [reload]);
  const run = useCallback(
    async <T,>(fn: () => Promise<T>, ok?: string): Promise<T | null> => {
      try {
        const res = await fn();
        if (res && typeof res === "object" && "watch" in (res as object)) setLive(res as unknown as LiveView);
        if (ok) toast({ kind: "ok", text: ok });
        return res;
      } catch (e) {
        if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
        return null;
      }
    },
    [toast],
  );
  return { live, setLive, reload, run };
}

function fmtWhen(at: number, lang: string) {
  try {
    return new Date(at * 1000).toLocaleString(lang, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch {
    return new Date(at * 1000).toLocaleString();
  }
}

// =========================================================================== auto clips (Pro)

export function AutoClipCard() {
  const { t, lang } = useI18n();
  const meta = useMeta();
  const { live, run } = useLive();
  const [folder, setFolder] = useState("");
  const fid = useId();
  if (!live) return null;
  const w = live.watch;
  const local = !!meta?.is_local;
  return (
    <section className="card setting" id="automation">
      <div>
        <h2>{t("auto.title")}</h2>
        <p>{t("auto.desc")}</p>
      </div>
      <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
        <div className="toggle-line">
          <span>
            <b>{t("auto.switch")}</b>
            <span className="muted ez-hint">{t("auto.switch_hint")}</span>
          </span>
          <Toggle checked={w.enabled} onChange={(v) => run(() => liveApi.watch({ enabled: v }), v ? t("auto.on_toast") : undefined)} label={t("auto.switch")} />
        </div>
        <div className="field">
          <span className="field-label">{t("auto.folders")}</span>
          {w.folders.length === 0 && <span className="notice"><Icon name="alert" /><span>{t("auto.no_folder")}</span></span>}
          {w.folders.map((f) => (
            <div className="sugg" key={f}>
              <Icon name="film" />
              <span className="mono" dir="ltr" style={{ overflowWrap: "anywhere" }}>{f}</span>
              {!w.custom_folders && <span className="chip chip-outline">{t("auto.obs_detected")}</span>}
              {w.custom_folders && local && (
                <button
                  className="btn btn-sm btn-ghost icon-btn"
                  aria-label={t("auto.remove_folder")}
                  title={t("auto.remove_folder")}
                  onClick={() => run(() => liveApi.watch({ folders: w.folders.filter((x) => x !== f) }))}
                >
                  <Icon name="x" />
                </button>
              )}
            </div>
          ))}
          {local && (
            <form
              className="lan-pin-row"
              onSubmit={(e) => {
                e.preventDefault();
                if (!folder.trim()) return;
                const base = w.custom_folders ? w.folders : [];
                run(() => liveApi.watch({ folders: [...base, folder.trim()] })).then((r) => r && setFolder(""));
              }}
            >
              <label htmlFor={fid} className="visually-hidden">{t("auto.add_folder")}</label>
              <input id={fid} className="input" dir="ltr" placeholder={w.detected ?? "C:\\Users\\…\\Videos"} value={folder} onChange={(e) => setFolder(e.target.value)} />
              <button className="btn btn-sm" type="submit" disabled={!folder.trim()}>
                <Icon name="plus" size={14} /> {t("auto.add_folder")}
              </button>
            </form>
          )}
          {w.custom_folders && w.detected && local && (
            <button className="link-btn" onClick={() => run(() => liveApi.watch({ folders: [] }))}>
              {t("auto.use_obs", { dir: w.detected })}
            </button>
          )}
        </div>
        <label className="field">
          <span className="field-label">{t("auto.render_top")}</span>
          <select className="select" value={w.render_top} onChange={(e) => run(() => liveApi.watch({ render_top: Number(e.target.value) }))}>
            {[3, 4, 6, 8, 10, 12].map((n) => (
              <option key={n} value={n}>{t("auto.render_n", { n: n })}</option>
            ))}
          </select>
        </label>
        <div className="field">
          <span className="field-label">{t("auto.publish")}</span>
          <Segmented<WatchPublish>
            block
            value={w.publish}
            label={t("auto.publish")}
            options={(["off", "plan", "now"] as WatchPublish[]).map((v) => ({ value: v, label: t(`auto.publish.${v}`) }))}
            onChange={(v) => run(() => liveApi.watch({ publish: v }))}
          />
          <span className="field-hint">
            {w.publish === "off" ? t("auto.publish_off_hint") : t("auto.publish_hint", { n: w.publish_top })}
          </span>
        </div>
        <label className="field">
          <span className="field-label">{t("auto.min_minutes")}</span>
          <select className="select" value={w.min_minutes} onChange={(e) => run(() => liveApi.watch({ min_minutes: Number(e.target.value) }))}>
            {[0, 2, 5, 10, 20].map((n) => (
              <option key={n} value={n}>{n === 0 ? t("auto.min_any") : t("auto.min_n", { n: n })}</option>
            ))}
          </select>
        </label>
        {w.recent.length > 0 && (
          <div className="field">
            <span className="field-label">{t("auto.recent")}</span>
            <ul className="auto-recent">
              {w.recent.map((r) => (
                <li key={r.path}>
                  <span className="mono" dir="ltr">{r.name}</span>
                  <span className={`chip ${r.status === "error" ? "chip-danger" : "chip-outline"}`}>
                    {r.status === "skipped" && r.reason ? t(`auto.skip.${r.reason}`) : t(`auto.status.${r.status}`)}
                  </span>
                  {r.project_id && (
                    <a className="link" href={`#/p/${encodeURIComponent(r.project_id)}`}>{t("auto.open")}</a>
                  )}
                  {!!r.markers && <span className="muted">{t("auto.markers_n", { n: r.markers })}</span>}
                  <span className="muted">{fmtWhen(r.at, lang)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {w.enabled && (
          <button className="btn btn-sm btn-ghost" style={{ justifySelf: "start" }} onClick={() => run(() => liveApi.scan(), t("auto.checked"))}>
            <Icon name="refresh" size={14} /> {t("auto.check_now")}
          </button>
        )}
      </div>
    </section>
  );
}

// =========================================================================== live markers (Pro)

export function MarkersCard() {
  const { t, lang } = useI18n();
  const { live, run, reload } = useLive();
  const [key, setKey] = useState<string | null>(null);
  const [channel, setChannel] = useState<string | null>(null);
  const [cmd, setCmd] = useState<string | null>(null);
  const [obs, setObs] = useState<{ ok: boolean; reason?: string; obs?: string } | null>(null);
  const kid = useId();
  const cid = useId();
  const mid = useId();
  useEffect(() => {
    liveApi.obsCheck().then(setObs).catch(() => {});
  }, []);
  if (!live) return null;
  const m = live.markers;
  const hk = live.service.hotkey;
  const tw = live.service.twitch;
  const yt = live.service.youtube;
  return (
    <section className="card setting" id="markers">
      <div>
        <h2>{t("mark.title")}</h2>
        <p>{t("mark.desc")}</p>
      </div>
      <div style={{ display: "grid", gap: 14, alignContent: "start" }}>
        <div className="field">
          <span className="field-label">{t("mark.hotkey")}</span>
          <div className="toggle-line">
            <form
              className="lan-pin-row"
              onSubmit={(e) => {
                e.preventDefault();
                if (key != null) run(() => liveApi.markers({ hotkey: key }), t("common.saved")).then(() => setKey(null));
              }}
            >
              <label htmlFor={kid} className="visually-hidden">{t("mark.hotkey")}</label>
              <input id={kid} className="input mono" dir="ltr" style={{ maxWidth: 200 }} value={key ?? m.hotkey} onChange={(e) => setKey(e.target.value)} disabled={!m.hotkey_supported} />
              {key != null && key !== m.hotkey && (
                <button className="btn btn-sm" type="submit">{t("common.save")}</button>
              )}
            </form>
            <Toggle checked={m.hotkey_enabled} onChange={(v) => run(() => liveApi.markers({ hotkey_enabled: v }))} label={t("mark.hotkey")} />
          </div>
          <span className={`field-hint${hk === "taken" || hk === "invalid" ? " warn-text" : ""}`}>
            {!m.hotkey_supported ? t("mark.hotkey_unsupported") : t(`mark.hotkey_status.${hk}`)}
          </span>
        </div>
        <div className="field">
          <span className="field-label">{t("mark.obs")}</span>
          <span className={`sugg${obs?.ok ? "" : " muted"}`}>
            <Icon name={obs?.ok ? "check" : "clock"} />
            <span>{obs == null ? t("common.loading") : obs.ok ? t("mark.obs_ok", { v: obs.obs ?? "" }) : t(`mark.obs.${obs.reason ?? "not_running"}`)}</span>
          </span>
          <span className="field-hint">{t("mark.obs_hint")}</span>
        </div>
        <label className="field" htmlFor={cid}>
          <span className="field-label">{t("mark.twitch")}</span>
        </label>
        <form
          className="lan-pin-row"
          style={{ marginTop: -10 }}
          onSubmit={(e) => {
            e.preventDefault();
            if (channel != null) run(() => liveApi.markers({ twitch_channel: channel }), t("common.saved")).then(() => setChannel(null));
          }}
        >
          <input id={cid} className="input" dir="ltr" placeholder={t("mark.twitch_ph")} value={channel ?? m.twitch_channel} onChange={(e) => setChannel(e.target.value)} />
          {channel != null && channel !== m.twitch_channel && <button className="btn btn-sm" type="submit">{t("common.save")}</button>}
        </form>
        {tw && <span className="field-hint" style={{ marginTop: -8 }}>{t(`mark.reader.${tw.status}`, { ch: tw.channel })}</span>}
        <div className="toggle-line">
          <span>
            <b>{t("mark.youtube")}</b>
            <span className="muted ez-hint">{yt ? t(`mark.reader.${yt.status}`, { ch: "YouTube" }) : t("mark.youtube_hint")}</span>
          </span>
          <Toggle checked={m.youtube_chat} onChange={(v) => run(() => liveApi.markers({ youtube_chat: v }))} label={t("mark.youtube")} />
        </div>
        <div className="field">
          <label className="field-label" htmlFor={mid}>{t("mark.command")}</label>
          <form
            className="lan-pin-row"
            onSubmit={(e) => {
              e.preventDefault();
              if (cmd != null) run(() => liveApi.markers({ command: cmd }), t("common.saved")).then(() => setCmd(null));
            }}
          >
            <input id={mid} className="input mono" dir="ltr" style={{ maxWidth: 160 }} value={cmd ?? m.command} onChange={(e) => setCmd(e.target.value)} />
            {cmd != null && cmd !== m.command && <button className="btn btn-sm" type="submit">{t("common.save")}</button>}
          </form>
          <span className="field-hint">{t("mark.command_hint", { cmd: m.command })}</span>
        </div>
        <div className="field">
          <span className="field-label">{t("mark.recent")}</span>
          {m.recent.length === 0 ? (
            <span className="muted">{t("mark.none")}</span>
          ) : (
            <ul className="auto-recent">
              {m.recent.map((x) => (
                <li key={x.id}>
                  <span className="chip chip-outline">{t(`mark.src.${x.source}`)}</span>
                  {x.by && <span>{x.by}</span>}
                  <span className="muted">{fmtWhen(x.at, lang)}</span>
                  {x.rec_ms != null && <span className="muted mono">REC {new Date(x.rec_ms).toISOString().slice(11, 19)}</span>}
                  <button className="btn btn-sm btn-ghost icon-btn" aria-label={t("mark.delete")} title={t("mark.delete")} onClick={() => run(() => liveApi.unmark(x.id)).then(reload)}>
                    <Icon name="trash" size={13} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <button className="btn btn-sm btn-ghost" style={{ justifySelf: "start" }} onClick={() => run(() => liveApi.mark(), t("mark.added")).then(reload)}>
            <Icon name="plus" size={14} /> {t("mark.now")}
          </button>
        </div>
      </div>
    </section>
  );
}

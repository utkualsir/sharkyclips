// 1.2.70 assisted upload, on every screen: what SharkyClips is doing in your browser right now
// ("Uploading the video…", "Everything is ready. Check and click Post.", "Log in once",
// "Please complete this in the browser"), the one-time helper-extension guide, "Did you post it?
// Yes / No", and the way out to posting by hand. SharkyClips never clicks Post for you.
import { useCallback, useEffect, useRef, useState } from "react";
import { ASSIST_LIVE, assistApi, assistKey, type AssistTask, type AssistView } from "../assist";
import { useI18n } from "../i18n";
import { TARGET_NAME, openHandoff } from "../multipost";
import { shareChanged } from "../share";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Modal } from "./ui";

export function AssistBar() {
  const { t } = useI18n();
  const toast = useToast();
  const [v, setV] = useState<AssistView | null>(null);
  const [guide, setGuide] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const last = useRef("");
  const load = useCallback(
    () =>
      assistApi
        .view()
        .then((d) => {
          setV(d);
          const sig = d.tasks.map((x) => `${x.id}:${x.state}:${x.setup ? 1 : 0}`).join(",");
          if (sig !== last.current) {
            if (last.current) shareChanged(); // the Share board follows along
            last.current = sig;
          }
          return d;
        })
        .catch(() => null),
    [],
  );
  const live = (v?.tasks ?? []).filter((x) => ASSIST_LIVE.includes(x.state) || x.state === "confirm");
  const active = live.length > 0;
  useEffect(() => {
    load();
    const iv = window.setInterval(() => document.visibilityState === "visible" && load(), active ? 2500 : 10000);
    const on = () => load();
    const openGuide = () => {
      setGuide(true);
      load();
    };
    window.addEventListener("sc-share-changed", on);
    window.addEventListener("sc-assist-guide", openGuide);
    return () => {
      window.clearInterval(iv);
      window.removeEventListener("sc-share-changed", on);
      window.removeEventListener("sc-assist-guide", openGuide);
    };
  }, [load, active]);
  const needSetup = live.some((x) => x.setup && x.state === "opening");
  useEffect(() => {
    if (needSetup) setGuide(true);
  }, [needSetup]);

  const act = async (task: AssistTask, action: "show" | "posted" | "not_posted" | "skip" | "manual") => {
    setBusy(task.id + action);
    try {
      setV(await assistApi.act(task.id, action));
      shareChanged();
      if (action === "manual") openHandoff({ pid: task.project_id, cid: task.clip_id, title: task.title ?? undefined, platforms: [task.platform] });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      {active && (
        <div className="assist-bar" role="status" aria-live="polite">
          {live.slice(0, 3).map((task) => (
            <AssistRow key={task.id} task={task} busy={busy} onAct={act} onGuide={() => setGuide(true)} />
          ))}
          {live.length > 3 && <span className="muted assist-more">{t("assist.more", { n: live.length - 3 })}</span>}
        </div>
      )}
      {guide && v && <AssistGuide v={v} onClose={() => setGuide(false)} />}
    </>
  );
}

function AssistRow({
  task,
  busy,
  onAct,
  onGuide,
}: {
  task: AssistTask;
  busy: string | null;
  onAct: (t: AssistTask, a: "show" | "posted" | "not_posted" | "skip" | "manual") => void;
  onGuide: () => void;
}) {
  const { t } = useI18n();
  const name = TARGET_NAME[task.platform];
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (task.state !== "pause") return;
    const iv = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(iv);
  }, [task.state]);
  const waitS = task.until ? Math.max(0, Math.round(task.until - now)) : 0;
  const ready = task.state === "ready";
  const act = task.state === "login" || task.state === "captcha" || (task.setup && task.state === "opening");
  const ask = task.state === "confirm" || task.state === "tab_closed";
  const pct = task.state === "uploading" && task.progress != null ? Math.round(task.progress * 100) : null;
  const dis = (a: string) => busy === task.id + a;
  return (
    <div className={`assist-row${ready ? " is-ready" : act ? " is-act" : ask ? " is-ask" : ""}`}>
      <Icon name={ready ? "check" : act ? "alert" : ask ? "bell" : task.state === "pause" ? "clock" : "upload"} size={15} />
      <span className="assist-text" dir="auto">
        <b>{name}</b> <span className="muted">· {task.title}</span>
        <br />
        <span>
          {t(assistKey(task, task.platform), { p: name, s: waitS, pct: pct ?? 0, browser: task.browser_name ?? "" })}
          {pct != null && ` ${pct}%`}
        </span>
        {ready && task.notes && task.notes.length > 0 && <span className="muted assist-notes"> {task.notes.join(" ")}</span>}
      </span>
      <span className="assist-actions">
        {ask ? (
          <>
            <button type="button" className="btn btn-sm btn-primary" disabled={dis("posted")} onClick={() => onAct(task, "posted")}>
              <Icon name="check" size={13} /> {t("assist.yes")}
            </button>
            <button type="button" className="btn btn-sm" disabled={dis("not_posted")} onClick={() => onAct(task, "not_posted")}>
              {t("assist.no")}
            </button>
          </>
        ) : (
          <>
            {task.setup && task.state === "opening" ? (
              <button type="button" className="btn btn-sm btn-primary" onClick={onGuide}>
                <Icon name="settings" size={13} /> {t("assist.guide_open")}
              </button>
            ) : (
              task.state !== "pause" && (
                <button type="button" className={`btn btn-sm${ready || act ? " btn-primary" : ""}`} disabled={dis("show")} onClick={() => onAct(task, "show")}>
                  <Icon name="eye" size={13} /> {t("assist.show")}
                </button>
              )
            )}
            {(ready || task.state === "post_clicked") && (
              <button type="button" className="btn btn-sm" disabled={dis("posted")} onClick={() => onAct(task, "posted")}>
                {t("assist.i_posted")}
              </button>
            )}
            <button type="button" className="btn btn-sm btn-ghost" disabled={dis("manual")} onClick={() => onAct(task, "manual")}>
              <Icon name="copy" size={13} /> {t("assist.by_hand")}
            </button>
            <button type="button" className="btn btn-sm btn-ghost" disabled={dis("skip")} onClick={() => onAct(task, "skip")} aria-label={t("assist.skip_label", { title: task.title ?? "" })}>
              <Icon name="x" size={13} /> {t("assist.skip")}
            </button>
          </>
        )}
      </span>
    </div>
  );
}

/** 1.2.74: a Helper from Microsoft Edge Add-ons / Firefox Add-ons pairs once with a 6-digit code. */
function StorePairing() {
  const { t } = useI18n();
  const toast = useToast();
  const [code, setCode] = useState<{ code: string; until: number } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!code) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [code]);
  const left = code ? Math.max(0, Math.round((code.until - now) / 1000)) : 0;
  const show = () =>
    assistApi
      .pairCode()
      .then((r) => {
        setNow(Date.now());
        setCode({ code: r.code, until: Date.now() + r.expires_in * 1000 });
      })
      .catch((e: any) => toast({ kind: "err", text: e.message, hint: e.hint }));
  return (
    <div className="assist-store" data-testid="assist-store">
      <b>{t("assist.store_title")}</b>
      <p className="muted">{t("assist.store_body")}</p>
      {code && left > 0 ? (
        <p className="assist-code-row">
          <code className="assist-code" dir="ltr" aria-label={t("assist.store_code_label")}>
            {code.code.slice(0, 3)} {code.code.slice(3)}
          </code>
          <span className="muted">{t("assist.store_left", { m: Math.floor(left / 60), s: String(left % 60).padStart(2, "0") })}</span>
        </p>
      ) : (
        <button type="button" className="btn btn-sm" onClick={show} data-testid="assist-pair-code">
          <Icon name="link" size={13} /> {t("assist.store_btn")}
        </button>
      )}
    </div>
  );
}

/** The one-time guide: put the SharkyClips Helper into the SharkyClips browser profile. */
export function AssistGuide({ v, onClose }: { v: AssistView; onClose: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const b = v.browsers;
  const name = b.using_name ?? "";
  const seen = v.ext.seen_at > 0;
  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <Modal title={t("assist.guide_title")} onClose={onClose} wide>
      {seen ? (
        <p className="notice assist-ok" role="status">
          <Icon name="check" /> {t("assist.guide_done")}
        </p>
      ) : (
        <p className="muted">{t(v.ext.autoload ? "assist.guide_lede_auto" : "assist.guide_lede", { browser: name })}</p>
      )}
      {!b.fills ? (
        <p className="notice notice-warn" role="note">
          <Icon name="alert" /> {t("assist.no_fill_browser", { browser: name || "Firefox" })}
        </p>
      ) : (
        <ol className="assist-steps">
          <li>
            <b>{t("assist.g1_title")}</b>
            <p className="muted">{t("assist.g1_body", { page: v.ext.page ?? "chrome://extensions" })}</p>
            <button type="button" className="btn btn-sm" onClick={() => run(() => assistApi.setup("extensions"))}>
              <Icon name="globe" size={13} /> {t("assist.g1_btn", { browser: name })}
            </button>
          </li>
          <li>
            <b>{t("assist.g2_title")}</b>
            <p className="muted">{t("assist.g2_body")}</p>
          </li>
          <li>
            <b>{t("assist.g3_title")}</b>
            <p className="muted">{t("assist.g3_body")}</p>
            <code className="assist-path" dir="ltr">{v.ext.dir}</code>
            <span className="assist-path-btns">
              <button
                type="button"
                className="btn btn-sm"
                onClick={() =>
                  navigator.clipboard
                    .writeText(v.ext.dir)
                    .then(() => toast({ kind: "ok", text: t("assist.copied") }))
                    .catch(() => {})
                }
              >
                <Icon name="copy" size={13} /> {t("assist.copy_path")}
              </button>
              <button type="button" className="btn btn-sm" onClick={() => run(() => assistApi.setup("folder"))}>
                <Icon name="file" size={13} /> {t("assist.open_folder")}
              </button>
            </span>
          </li>
          <li>
            <b>{t("assist.g4_title")}</b>
            <p className="muted">{t("assist.g4_body")}</p>
          </li>
        </ol>
      )}
      <StorePairing />
      <p className="muted assist-safe">
        <Icon name="lock" size={13} /> {t("assist.guide_safe")}
      </p>
    </Modal>
  );
}

/** Settings > Accounts / Publishing: which browser, the pause between posts, log in once, the guide. */
export function AssistSettings({ platform }: { platform: "tiktok" | "reels" }) {
  const { t } = useI18n();
  const toast = useToast();
  const [v, setV] = useState<AssistView | null>(null);
  const [guide, setGuide] = useState(false);
  useEffect(() => {
    assistApi.view().then(setV).catch(() => {});
  }, []);
  if (!v) return null;
  const b = v.browsers;
  const run = async (fn: () => Promise<AssistView | unknown>) => {
    try {
      const r = await fn();
      if (r && typeof r === "object" && "browsers" in (r as AssistView)) setV(r as AssistView);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const selId = `assist-browser-${platform}`;
  const pauseId = `assist-pause-${platform}`;
  return (
    <div className="assist-settings">
      <p className="acc-note" role="note">
        {t("assist.how", { p: TARGET_NAME[platform] })}
      </p>
      <div className="assist-settings-row">
        <label className="field" htmlFor={selId}>
          <span className="field-label">{t("assist.browser")}</span>
          <select
            id={selId}
            className="input"
            value={b.chosen}
            onChange={(e) => run(() => assistApi.settings({ browser: e.target.value }))}
          >
            <option value="auto">{t("assist.browser_auto", { name: b.installed.find((x) => x.key === b.default)?.name ?? b.using_name ?? "—" })}</option>
            {b.installed.map((x) => (
              <option key={x.key} value={x.key}>
                {x.name}
                {x.fills ? "" : ` (${t("assist.by_hand_only")})`}
              </option>
            ))}
          </select>
        </label>
        {platform === "tiktok" && (
          <label className="field" htmlFor={pauseId}>
            <span className="field-label">{t("assist.pause")}</span>
            <input
              id={pauseId}
              className="input"
              type="number"
              min={20}
              max={600}
              value={v.pause_s}
              onChange={(e) => {
                const n = Math.max(20, Math.min(600, Number(e.target.value) || 60));
                setV({ ...v, pause_s: n });
                assistApi.settings({ pause_s: n }).catch(() => {});
              }}
            />
          </label>
        )}
      </div>
      {!b.fills && b.using_name && (
        <p className="notice notice-warn" role="note">
          <Icon name="alert" /> {t("assist.no_fill_browser", { browser: b.using_name })}
        </p>
      )}
      <div className="assist-settings-btns">
        <button type="button" className="btn btn-sm" onClick={() => run(() => assistApi.open(platform))}>
          <Icon name="globe" size={13} /> {t("assist.login_once", { p: TARGET_NAME[platform] })}
        </button>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => setGuide(true)}>
          <Icon name="settings" size={13} /> {t(v.ext.seen_at > 0 ? "assist.helper_ok" : "assist.helper_setup")}
        </button>
      </div>
      {guide && <AssistGuide v={v} onClose={() => setGuide(false)} />}
    </div>
  );
}

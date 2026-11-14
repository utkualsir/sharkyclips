// 1.2.42 Settings → Accounts → TikTok: automatic posts through TikTok Studio in SharkyClips' own
// browser profile (you log in yourself once; only the browser profile is kept, never a password),
// plus the "Automatic / Semi-automatic" switch per platform and the publish-queue check.
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { accountsApi, isAuto, TARGET_NAME, type Account, type TikTokBrowser } from "../multipost";
import { useToast } from "../toast";
import { Icon } from "./Icons";

function BrowserPill({ b }: { b: TikTokBrowser }) {
  const { t } = useI18n();
  const pill = b.pill === "not_connected" ? "signed_out" : b.pill;
  return (
    <span className={`acc-pill acc-pill-${pill}`}>
      <span className="acc-dot" aria-hidden="true" />
      {t(`tts.pill_${b.pill}`)}
    </span>
  );
}

/** The TikTok Studio login: "Log in to TikTok" opens a visible window, the rest happens there. */
export function TikTokStudioBox({ a, onChange }: { a: Account; onChange: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [b, setB] = useState<TikTokBrowser | null>(a.browser ?? null);
  const [busy, setBusy] = useState(false);
  const poll = useRef<number | null>(null);
  useEffect(() => setB(a.browser ?? null), [a.browser]);
  useEffect(() => () => {
    if (poll.current) window.clearInterval(poll.current);
  }, []);
  const LIVE = ["opening", "waiting", "checking"];
  const waiting = LIVE.includes(b?.login.state ?? "");
  const watch = () => {
    if (poll.current) window.clearInterval(poll.current);
    poll.current = window.setInterval(async () => {
      try {
        const s = await accountsApi.tbStatus();
        setB(s);
        if (!LIVE.includes(s.login.state)) {
          if (poll.current) window.clearInterval(poll.current);
          poll.current = null;
          if (s.login.state === "done") toast({ kind: "ok", text: t("tts.login_ok", { name: s.username ? `@${s.username}` : "TikTok" }) });
          if (s.login.state === "error") toast({ kind: "err", text: s.login.error || t("tts.login_failed") });
          if (s.login.state === "not_logged_in") toast({ kind: "err", text: t("tts.not_logged_in") });
          onChange();
        }
      } catch {
        /* the server restarts: try again */
      }
    }, 2000);
  };
  useEffect(() => {
    if (waiting && !poll.current) watch(); // the page was reloaded while the login window is open
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting]);
  const run = async (fn: () => Promise<TikTokBrowser>, ok?: string) => {
    setBusy(true);
    try {
      const s = await fn();
      setB(s);
      if (ok) toast({ kind: "ok", text: ok });
      onChange();
      return s;
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(false);
    }
  };
  if (!b) return null;
  const logged = b.logged_in;
  return (
    <div className="tts-box" role="group" aria-labelledby="tts-title">
      <div className="tts-head">
        <b id="tts-title">{t("tts.title")}</b>
        <BrowserPill b={b} />
      </div>
      {logged && b.username && (
        <p className="tts-user" dir="auto">
          <Icon name="check" size={14} /> {t("tts.as", { name: `@${b.username}` })}
        </p>
      )}
      <p className="acc-note" role="note">
        <Icon name="lock" size={14} /> {t("tts.privacy")}
      </p>
      {!b.available && (
        <p className="acc-note acc-note-warn" role="note">
          <Icon name="alert" size={14} /> {t("tts.no_playwright")}
        </p>
      )}
      {b.blocked && (
        <p className="acc-note acc-note-warn" role="alert">
          <Icon name="alert" size={14} /> {t(`tts.stop_${b.blocked.reason}`)} {t("tts.stopped_hint")}
        </p>
      )}
      {waiting && (
        <p className="acc-note" role="status">
          <Icon name="clock" size={14} /> {t(b.login.state === "checking" ? "tts.checking" : "tts.waiting")}
        </p>
      )}
      <div className="acc-actions">
        {!waiting ? (
          <button
            className={`btn btn-sm${logged ? "" : " btn-primary"}`}
            disabled={busy || !b.available}
            onClick={async () => {
              const s = await run(() => accountsApi.tbLogin());
              if (s) watch();
            }}
          >
            <Icon name="link" /> {t(logged ? "tts.login_again" : "tts.login")}
          </button>
        ) : (
          <button className="btn btn-sm btn-ghost" onClick={() => run(() => accountsApi.tbCancel())}>
            <Icon name="x" /> {t("tts.cancel")}
          </button>
        )}
        {(b.login_at || b.profile) && !waiting && (
          <button className="btn btn-sm btn-ghost" disabled={busy || b.busy} onClick={() => run(() => accountsApi.tbCheck(), t("tts.check_ok"))}>
            <Icon name="check" /> {t("tts.check")}
          </button>
        )}
        {b.login_at && !waiting && (
          <button
            className="btn btn-sm btn-ghost btn-danger-text"
            disabled={busy}
            onClick={() => window.confirm(t("tts.logout_q")) && run(() => accountsApi.tbLogout())}
          >
            <Icon name="power" /> {t("tts.logout")}
          </button>
        )}
      </div>
      {logged && (
        <label className="field tts-cap">
          <span className="field-label">{t("tts.daily")}</span>
          <input
            className="input"
            type="number"
            min={1}
            max={15}
            value={b.daily_cap}
            onChange={(e) => {
              const n = Math.max(1, Math.min(15, Number(e.target.value) || 1));
              setB({ ...b, daily_cap: n });
              accountsApi.tbSettings({ daily_cap: n }).catch(() => {});
            }}
          />
          <span className="muted tts-cap-note">{t("tts.daily_note", { n: num(b.daily_cap) })}</span>
        </label>
      )}
    </div>
  );
}

/** Automatic / Semi-automatic, per platform. Automatic needs a working account
 *  (Instagram: the API; TikTok: the TikTok Studio login, or the TikTok API). */
export function AutoSwitch({ a, onChange }: { a: Account; onChange: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const p = a.platform as "tiktok" | "reels";
  const viaBrowser = p === "tiktok" && (a.via === "browser" || !a.connected);
  const canAuto = p === "tiktok" ? Boolean(a.browser?.logged_in) || (a.connected && a.via !== "browser") : a.connected;
  const auto = isAuto(a.mode);
  const set = async (on: boolean) => {
    try {
      await accountsApi.setMode(p, on ? (p === "tiktok" && (viaBrowser || a.browser?.logged_in) ? "browser" : "api") : "semi");
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    onChange();
  };
  return (
    <div className="tts-switch">
      <div className="segmented block" role="radiogroup" aria-label={t("tts.mode_label", { name: TARGET_NAME[p] })}>
        <button type="button" role="radio" aria-checked={auto} disabled={!canAuto && !auto} onClick={() => set(true)}>
          <Icon name="zap" size={14} /> {t("tts.auto")}
        </button>
        <button type="button" role="radio" aria-checked={!auto} onClick={() => set(false)}>
          <Icon name="copy" size={14} /> {t("tts.semi")}
        </button>
      </div>
      <p className="acc-note" role="note">
        {auto
          ? t(p === "tiktok" && a.mode === "browser" ? "tts.auto_browser" : "platform.mode_api", { name: TARGET_NAME[p] })
          : t("platform.mode_semi", { name: TARGET_NAME[p] })}
        {!canAuto && !auto && <> {t(p === "tiktok" ? "tts.auto_needs_login" : "tts.auto_needs_connect")}</>}
      </p>
    </div>
  );
}

/** Publish queue: look up the overdue posts on TikTok (TikTok Studio) and Instagram (API). */
export function ReconcileButton({ onDone }: { onDone?: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <button
      className="btn btn-sm"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await accountsApi.reconcile();
          toast({ kind: "info", text: t("tts.reconcile_started") });
          window.setTimeout(() => onDone?.(), 8000);
        } catch (e: any) {
          toast({ kind: "err", text: e.message, hint: e.hint });
        } finally {
          setBusy(false);
        }
      }}
    >
      <Icon name="refresh" /> {t("tts.reconcile")}
    </button>
  );
}

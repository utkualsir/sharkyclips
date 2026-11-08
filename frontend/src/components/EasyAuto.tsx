import { useCallback, useEffect, useState } from "react";
import { ApiError, easyApi, type AutopilotView, type EasyHealth } from "../api";
import { useI18n } from "../i18n";
import { href } from "../router";
import { useToast } from "../toast";
import { useUiMode } from "../uimode";
import { Icon } from "./Icons";
import { Modal, Toggle } from "./ui";
import { ConnectPrompt } from "./YoutubeConnect";

/** 1.2.34: the YouTube connection at a glance: green / amber / red, one tap to fix. */
export function ConnectionPill() {
  const { t, num } = useI18n();
  const [h, setH] = useState<EasyHealth | null>(null);
  const [open, setOpen] = useState(false);
  const [checking, setChecking] = useState(false);
  const load = useCallback((probe = false) => easyApi.health(probe).then(setH).catch(() => {}), []);
  useEffect(() => {
    load();
    const iv = window.setInterval(() => document.visibilityState === "visible" && load(), 60000);
    return () => window.clearInterval(iv);
  }, [load]);
  if (!h) return null;
  const label =
    h.code === "connected" || h.code === "locked"
      ? h.channel
        ? t("easy2.yt_ok_channel", { channel: h.channel })
        : t("easy2.yt_ok")
      : h.code === "attention"
        ? t("easy2.yt_attention", { n: num(h.count ?? 0) })
        : t(`easy2.yt_${h.code}`);
  return (
    <>
      <button type="button" className={`ez-pill ez-pill-${h.state}`} onClick={() => setOpen(true)} aria-haspopup="dialog">
        <span className="ez-dot" aria-hidden="true" />
        <span className="ez-pill-text">{label}</span>
      </button>
      {open && (
        <Modal title={t("easy2.yt_title")} onClose={() => setOpen(false)}>
          <p style={{ marginTop: 0 }}>{t(`easy2.yt_body_${h.code}`)}</p>
          {h.message && <p className="muted">{h.message}</p>}
          {(h.fix === "connect" || h.fix === "reconnect") && (
            <ConnectPrompt
              onConnected={() => {
                setOpen(false);
                load(true);
              }}
            />
          )}
          {h.fix === "library" && (
            <a className="btn btn-primary" href={href.publish()} onClick={() => setOpen(false)}>
              {t("easy2.yt_open_library")}
            </a>
          )}
          {!h.fix && (
            <button
              className="btn"
              disabled={checking}
              onClick={async () => {
                setChecking(true);
                await load(true);
                setChecking(false);
              }}
            >
              {checking ? <span className="spinner" /> : <Icon name="refresh" />} {t("easy2.yt_check")}
            </button>
          )}
        </Modal>
      )}
    </>
  );
}

/** 1.2.34 Autopilot: one switch for recording -> clips -> bleeps -> texts -> covers -> plan. */
export function AutopilotCard() {
  const { t, num } = useI18n();
  const toast = useToast();
  const { update, setMode } = useUiMode();
  const [v, setV] = useState<AutopilotView | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    easyApi.autopilot().then(setV).catch(() => {});
  }, []);

  const flip = async (on: boolean) => {
    setBusy(true);
    try {
      await easyApi.saveSettings({ autopilot: on }); // errors (no recordings folder) are shown
      await update({});
      const nv = await easyApi.autopilot();
      setV(nv);
      if (on && nv.enabled) toast({ kind: "ok", text: t("easy2.ap_on_toast"), hint: t("easy2.ap_on_hint", { h: num(nv.summary_hour) }) });
    } catch (e) {
      if (e instanceof ApiError)
        toast({ kind: "err", text: e.message, hint: e.hint, action: { label: t("easy.switch_to_pro"), run: () => setMode("pro") } });
      easyApi.autopilot().then(setV).catch(() => {});
    } finally {
      setBusy(false);
    }
  };

  const steps = ["rec", "clips", "bleeps", "texts", "covers", "plan"] as const;
  return (
    <section className="card ez-set-card ez-ap" aria-labelledby="ez-set-ap">
      <div className="toggle-line">
        <span>
          <h2 id="ez-set-ap" style={{ margin: 0 }}>
            <Icon name="zap" size={18} /> {t("easy2.ap_title")}
          </h2>
          <span className="muted ez-hint">{t("easy2.ap_hint")}</span>
        </span>
        <Toggle checked={!!v?.enabled} onChange={(on) => !busy && flip(on)} label={t("easy2.ap_title")} />
      </div>
      <ol className="ez-ap-chain" aria-label={t("easy2.ap_title")}>
        {steps.map((s) => (
          <li key={s} className={v?.enabled ? "on" : ""}>
            {t(`easy2.ap_step_${s}`)}
          </li>
        ))}
      </ol>
      {v?.enabled && (
        <div className="ez-ap-state">
          <ConnectionPill />
          <span className="muted">{v.summary.ready || v.summary.waiting ? v.summary.text : t("easy2.ap_nothing_yet")}</span>
        </div>
      )}
    </section>
  );
}

const PHONE_KEY = "sc-phone-preview";

export function usePhonePreview(): [boolean, (v: boolean) => void] {
  const [on, setOn] = useState(() => {
    try {
      return localStorage.getItem(PHONE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const set = (v: boolean) => {
    setOn(v);
    try {
      localStorage.setItem(PHONE_KEY, v ? "1" : "0");
    } catch {
      /* private mode: this session only */
    }
  };
  return [on, set];
}

/** 1.2.34: the Shorts player's own buttons, title area and progress bar drawn over the clip
 *  (1080x1920 coordinates, the same safe zone the renderer keeps text out of). */
export function ShortsOverlay({ title, channel }: { title: string; channel?: string | null }) {
  const { t } = useI18n();
  const icons: [number, string][] = [
    [1010, "M-22 4v28M-6 -10l-4 14h22a6 6 0 0 1 6 7l-5 17a6 6 0 0 1-6 4h-35"],
    [1175, "M-22 -4v-28M-6 10l-4 -14h22a6 6 0 0 0 6 -7l-5 -17a6 6 0 0 0 -6 -4h-35"],
    [1340, "M-26 -18h52v34h-30l-14 12v-12h-8z"],
    [1505, "M8 -22l26 22-26 22v-12c-22 0-34 6-42 20 2-22 14-36 42-38z"],
    [1665, "M-24 -14a26 26 0 0 1 46 -6M24 14a26 26 0 0 1 -46 6M22 -30v12h-12M-22 30v-12h12"],
  ];
  return (
    <div className="ez-phone" aria-hidden="true">
      <svg viewBox="0 0 1080 1920" preserveAspectRatio="none">
        <defs>
          <linearGradient id="ezp-top" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#000" stopOpacity="0.55" />
            <stop offset="1" stopColor="#000" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="ezp-bot" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#000" stopOpacity="0" />
            <stop offset="1" stopColor="#000" stopOpacity="0.6" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="1080" height="220" fill="url(#ezp-top)" />
        <rect x="0" y="1400" width="1080" height="520" fill="url(#ezp-bot)" />
        <g fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="880" cy="90" r="26" />
          <path d="M900 110l22 22" />
          <path d="M1000 62v0M1000 90v0M1000 118v0" strokeWidth="14" />
          {icons.map(([y, d]) => (
            <path key={y} d={d} transform={`translate(985 ${y})`} />
          ))}
        </g>
        <rect x="945" y="1770" width="80" height="80" rx="16" fill="#fff" fillOpacity="0.85" />
        <circle cx="95" cy="1640" r="38" fill="#fff" fillOpacity="0.9" />
        <rect x="370" y="1612" width="170" height="56" rx="28" fill="#fff" />
        <rect x="0" y="1904" width="1080" height="8" fill="#fff" fillOpacity="0.35" />
        <rect x="0" y="1904" width="380" height="8" fill="#ff0033" />
        <rect x="40" y="140" width="900" height="1400" fill="none" stroke="#7fd4ff" strokeWidth="4" strokeDasharray="18 14" opacity="0.7" />
      </svg>
      <span className="ez-phone-channel">@{channel || "channel"}</span>
      <span className="ez-phone-sub">{t("easy2.phone_subscribe")}</span>
      <span className="ez-phone-title" dir="auto">
        {title}
      </span>
    </div>
  );
}

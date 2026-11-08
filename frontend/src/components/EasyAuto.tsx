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

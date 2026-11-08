import { useState } from "react";
import { ApiError, easyApi, type EasyClip, type EasyView, type NudgeAction } from "../api";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon, type IconName } from "./Icons";

/** Easy 2.0 (1.2.34): what the smart cut did + one-tap nudges (start earlier, end later,
 *  short / long version, back to the smart cut). */
export function CutRow({ pid, c, disabled, onView }: { pid: string; c: EasyClip; disabled: boolean; onView: (v: EasyView) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState<NudgeAction | null>(null);
  const sh = c.shape;
  if (!sh) return null;

  const run = async (a: NudgeAction) => {
    setBusy(a);
    try {
      onView(await easyApi.nudge(pid, c.id, a));
      toast({ kind: "ok", text: t("easy2.nudged"), hint: t("easy.saved_rerender") });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(null);
    }
  };

  const why = sh.why.slice(0, 2);
  const btn = (a: NudgeAction, icon: IconName, label: string) => (
    <button type="button" className="ez-nudge" onClick={() => run(a)} disabled={disabled || busy !== null}>
      {busy === a ? <span className="spinner" /> : <Icon name={icon} size={14} />}
      <span>{label}</span>
    </button>
  );

  return (
    <div className="ez-cut">
      {why.length > 0 && (
        <p className="ez-cut-why">
          <Icon name="scissors" size={14} />
          <span>{why.map((w) => t(`easy2.why_${w}`)).join(" · ")}</span>
        </p>
      )}
      {sh.length && (
        <p className={`ez-cut-len${sh.length === "very_long" ? " warn" : ""}`}>
          <Icon name="alert" size={14} />
          <span>
            {t(`easy2.len_${sh.length}`, { s: num(Math.round(c.duration)), max: num(sh.target.max) })}
          </span>
        </p>
      )}
      <div className="ez-nudges" role="group" aria-label={t("easy2.nudge_group")}>
        {btn("earlier", "chevron-left", t("easy2.earlier"))}
        {btn("later", "chevron-right", t("easy2.later"))}
        {btn("short", "minus", t("easy2.short"))}
        {btn("long", "plus", t("easy2.long"))}
        {!sh.auto && sh.shaped && btn("auto", "sparkles", t("easy2.back_auto"))}
      </div>
    </div>
  );
}

/** Older projects: one tap switches the smart cuts on. */
export function SmartBanner({ pid, onView }: { pid: string; onView: (v: EasyView) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <div className="notice ez-smart" role="note">
      <Icon name="sparkles" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="notice-title">{t("easy2.smart_title")}</div>
        <div className="muted">{t("easy2.smart_body")}</div>
      </div>
      <button
        className="btn btn-primary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            onView(await easyApi.smart(pid, true));
          } catch (e) {
            if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy && <span className="spinner" />} {t("easy2.smart_on")}
      </button>
    </div>
  );
}

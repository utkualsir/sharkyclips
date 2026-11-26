// 1.2.66: "3 of 5 left today" - the daily upload limit, always in sight (top bar, Share board).
import { useEffect, useState } from "react";
import "../share.css";
import { useI18n } from "../i18n";
import { href } from "../router";
import { shareApi, type DailyLimit } from "../share";
import { Icon } from "./Icons";

export function useDailyLimit(seed?: DailyLimit | null): DailyLimit | null {
  const [v, setV] = useState<DailyLimit | null>(seed ?? null);
  useEffect(() => {
    if (seed) setV(seed);
  }, [seed]);
  useEffect(() => {
    let alive = true;
    const load = () =>
      shareApi
        .limit()
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
  return v;
}

/** The pill: "3 of 5 left today" (short "3/5" on narrow top bars). Links to the setting. */
export function UploadsLeft({ value, big }: { value?: DailyLimit | null; big?: boolean }) {
  const { t, num } = useI18n();
  const v = useDailyLimit(value);
  if (!v) return null;
  const full = v.left <= 0;
  const text = t("share.left_today", { left: num(v.left), limit: num(v.limit) });
  return (
    <a
      className={`uploads-left${full ? " is-full" : ""}${big ? " is-big" : ""}`}
      href={`${href.settings}/limit`}
      title={`${text} · ${t("share.limit_change")}`}
      aria-label={`${text}. ${t("share.limit_change")}`}
    >
      <Icon name="upload" size={big ? 15 : 13} />
      <span className="ul-long">{text}</span>
      <span className="ul-short mono" aria-hidden="true">
        {num(v.left)}/{num(v.limit)}
      </span>
    </a>
  );
}

/** The setting itself (Settings in both modes): 1 .. 6 a day. */
export function DailyLimitField({ withLabel = true }: { withLabel?: boolean }) {
  const { t, num } = useI18n();
  const v = useDailyLimit();
  const [busy, setBusy] = useState(false);
  const shown = !!v;
  useEffect(() => {
    // opened from the pill (#/settings/limit): bring the setting into view
    if (shown && /\/limit$/.test(window.location.hash))
      document.getElementById("daily-limit")?.scrollIntoView({ block: "center" });
  }, [shown]);
  if (!v) return null;
  const set = (n: number) => {
    setBusy(true);
    shareApi
      .setLimit(n)
      .then(() => window.dispatchEvent(new CustomEvent("sc-share-changed")))
      .catch(() => {})
      .finally(() => setBusy(false));
  };
  return (
    <div className="daily-limit-field" id="daily-limit">
      <div style={{ minWidth: 0, flex: 1 }}>
        <div className={withLabel ? "field-label" : "visually-hidden"} id="daily-limit-label">
          {t("share.limit_title")}
        </div>
        <p className="field-hint" style={{ margin: 0 }}>
          {t("share.limit_hint", { max: num(v.max) })}{" "}
          <b>{t("share.left_today", { left: num(v.left), limit: num(v.limit) })}</b>
        </p>
      </div>
      <div className="stepper" role="group" aria-labelledby="daily-limit-label">
        <button
          type="button"
          className="btn icon-btn"
          onClick={() => set(v.limit - 1)}
          disabled={busy || v.limit <= 1}
          aria-label={t("share.limit_less")}
        >
          <Icon name="minus" />
        </button>
        <output className="stepper-value mono" aria-live="polite">
          {num(v.limit)}
        </output>
        <button
          type="button"
          className="btn icon-btn"
          onClick={() => set(v.limit + 1)}
          disabled={busy || v.limit >= v.max}
          aria-label={t("share.limit_more")}
        >
          <Icon name="plus" />
        </button>
      </div>
    </div>
  );
}

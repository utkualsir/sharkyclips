// 1.2.66 pill, 1.2.68 meaning: "X uploads left today" = what YouTube really allows today (its own
// upload quota, 100 a day by default). There is no daily limit setting any more.
import { useEffect, useState } from "react";
import "../share.css";
import { useI18n } from "../i18n";
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

/** The pill: "X YouTube uploads left today" (short "X" on narrow top bars). */
export function UploadsLeft({ value, big }: { value?: DailyLimit | null; big?: boolean }) {
  const { t, num } = useI18n();
  const v = useDailyLimit(value);
  if (!v || v.connected === false) return null;
  const full = v.left <= 0;
  // 1.2.75: the built-in client shares one pool with everyone: no made-up "X left"
  const exact = v.exact !== false;
  const text = full && v.mode === "shared"
    ? t("yq.exceeded_title")
    : exact
      ? t("share.uploads_left", { n: num(v.left) })
      : t("yq.shared_short", { n: num(v.mine_today ?? 0) });
  const reset = new Date(v.resets_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return (
    <span
      className={`uploads-left${full ? " is-full" : ""}${big ? " is-big" : ""}`}
      title={`${text} · ${t("share.uploads_reset", { time: reset })}`}
      role="status"
    >
      <Icon name="upload" size={big ? 15 : 13} />
      <span className="ul-long">{text}</span>
      <span className="ul-short mono" aria-hidden="true">
        {exact || full ? num(v.left) : "·"}
      </span>
    </span>
  );
}

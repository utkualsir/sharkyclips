import { useState } from "react";
import { bleepApi, type BleepReport, type BleepSummary } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon } from "./Icons";

/** 1.2.31: "7 bleeps ✅" or "2 swears could not be bleeped" on a rendered clip. */
export function BleepBadge({ s }: { s: BleepSummary | null | undefined }) {
  const { t, num } = useI18n();
  if (!s) return null;
  if (s.error) {
    return (
      <span className="bleep-badge warn" title={t("bleep.check_failed")}>
        <Icon name="alert" size={13} /> {t("bleep.check_failed")}
      </span>
    );
  }
  if (s.audible) {
    return (
      <span className="bleep-badge bad" role="status">
        <Icon name="alert" size={13} /> {t("bleep.badge_missing", { n: num(s.audible) })}
        {s.checked ? ` · ${t("bleep.checked")}` : ""}
      </span>
    );
  }
  if (!s.expected) return null;
  return (
    <span className="bleep-badge ok" title={t("bleep.report")}>
      {t("bleep.badge_ok", { n: num(s.bleeped ?? s.expected) })}
    </span>
  );
}

/** The "I listened, it's OK" button: lifts the upload hold of a clip with unresolved bleeps. */
export function BleepCheckedButton({ pid, cid, onDone }: { pid: string; cid: string; onDone?: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <div className="bleep-hold" role="alert">
      <span className="muted small">{t("bleep.hold_hint")}</span>
      <button
        className="btn btn-sm"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          bleepApi
            .checked(pid, cid, true)
            .then(() => onDone?.())
            .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }))
            .finally(() => setBusy(false));
        }}
      >
        <Icon name="check" size={14} /> {t("bleep.checked_btn")}
      </button>
    </div>
  );
}

/** Pro: every swear of the clip with its time in the file and a play button. */
export function BleepList({
  pid,
  cid,
  report,
  checked,
  videoId,
  onChanged,
}: {
  pid: string;
  cid: string;
  report: BleepReport | null | undefined;
  checked?: string | null;
  videoId: string;
  onChanged?: () => void;
}) {
  const { t, num } = useI18n();
  if (!report || report.error || !report.items?.length) return null;
  const play = (at: number) => {
    const v = document.getElementById(videoId) as HTMLVideoElement | null;
    if (!v) return;
    v.currentTime = Math.max(0, at - 0.8);
    void v.play();
    window.setTimeout(() => v.pause(), 2000);
  };
  const audible = report.audible ?? 0;
  return (
    <details className="bleep-list" open={audible > 0 && !checked}>
      <summary>
        {t("bleep.report")} · {audible ? t("bleep.badge_missing", { n: num(audible) }) : t("bleep.badge_ok", { n: num(report.bleeped ?? 0) })}
      </summary>
      <ul>
        {report.items.map((it, i) => (
          <li key={i} className={it.ok ? "" : "bad"}>
            <button className="btn btn-ghost icon-btn btn-sm" onClick={() => play(it.t)} aria-label={t("bleep.play")} title={t("bleep.play")}>
              <Icon name="play" size={13} />
            </button>
            <span className="mono">{fmtTime(it.t)}</span>
            <span className="bleep-word" dir="auto">{it.word}</span>
            {it.spk && <span className="chip chip-outline">{it.spk === "me" ? t("bleep.spk_me") : t("bleep.spk_friend")}</span>}
            {it.where.includes("flash") && <span className="chip chip-outline">{t("bleep.where_flash")}</span>}
            {it.where.includes("replay") && <span className="chip chip-outline">{t("bleep.where_replay")}</span>}
            <span className={it.ok ? "ok-text" : "warn-text"}>{it.ok ? t("bleep.item_ok") : t("bleep.item_audible")}</span>
          </li>
        ))}
      </ul>
      {audible > 0 && !checked && <BleepCheckedButton pid={pid} cid={cid} onDone={onChanged} />}
    </details>
  );
}

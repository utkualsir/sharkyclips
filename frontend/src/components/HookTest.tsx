import { useState } from "react";
import { api, urls, type Candidate, type HookReason, type HookTest, type HookTests } from "../api";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Modal } from "./ui";

// A/B hooks (1.2.5): the clip's two openings, the hook model's scores and reasons, and how the
// upload picks one (the real test on YouTube, or the pre-test's winner).

export function reasonText(r: HookReason, t: ReturnType<typeof useI18n>["t"], num: (n: number, d?: number) => string): string {
  const v = r.value;
  switch (r.code) {
    case "motion":
      return t("ab.reason.motion", { x: num(Number(v), 1) });
    case "loudness":
      return t("ab.reason.loudness", { db: num(Number(v), 1) });
    case "face":
      return t("ab.reason.face", { p: num(Math.round(Number(v) * 100)) });
    case "smile":
      return t("ab.reason.smile", { p: num(Math.round(Number(v) * 100)) });
    case "text_length":
      return t("ab.reason.text_length", { n: Number(v) });
    case "trigger_words":
      return t("ab.reason.trigger_words", { words: String(v) });
    case "reaction":
      return t("ab.reason.reaction");
    case "ai_judgment":
      return t("ab.reason.ai_judgment", { n: Number(v) });
    case "channel":
      return t("ab.reason.channel", { n: Number(v) });
    default:
      return t(`ab.reason.${r.code}`);
  }
}

export function RealTestNote({ realTest }: { realTest: HookTests["real_test"] | null }) {
  const { t } = useI18n();
  if (!realTest) return null;
  if (realTest.active) {
    return (
      <div className="notice">
        <Icon name="chart" />
        <span>{t("ab.real_active")}</span>
      </div>
    );
  }
  return (
    <div className={`notice ${realTest.reason === "locked_private" ? "notice-warn" : ""}`}>
      <Icon name={realTest.reason === "locked_private" ? "alert" : "clock"} />
      <span>
        {t(`ab.real_off.${realTest.reason ?? "not_connected"}`)}{" "}
        {realTest.reason !== "locked_private" && <a href="#/settings">{t("nav.settings")}</a>}
      </span>
    </div>
  );
}

export default function HookTestDialog({
  projectId,
  cand,
  test,
  realTest,
  busy,
  onUpload,
  onChanged,
  onClose,
}: {
  projectId: string;
  cand: Candidate;
  test: HookTest;
  realTest: HookTests["real_test"] | null;
  busy: boolean;
  onUpload: (source: string) => void;
  onChanged: () => void;
  onClose: () => void;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [working, setWorking] = useState(false);
  const pick = test.upload_pick.label ?? test.winner;

  const again = async () => {
    setWorking(true);
    try {
      await api.makeHookTest(projectId, cand.id);
      toast({ kind: "ok", text: t("ab.queued") });
      onClose();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setWorking(false);
  };
  const remove = async () => {
    if (!window.confirm(t("ab.delete_confirm"))) return;
    await api.deleteHookTest(projectId, cand.id).catch(() => {});
    onChanged();
    onClose();
  };

  return (
    <Modal
      title={t("ab.title", { n: cand.rank })}
      onClose={onClose}
      wide
      footer={
        <>
          <div className="export-sum">
            <button className="btn btn-ghost btn-sm" onClick={remove}>
              <Icon name="trash" />
              {t("common.delete")}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={again} disabled={working || busy}>
              <Icon name="refresh" />
              {t("ab.again")}
            </button>
          </div>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.close")}
          </button>
          {test.uploaded ? (
            <a className="btn btn-primary" href={test.uploaded.url} target="_blank" rel="noreferrer">
              <Icon name="link" />
              {t("ab.on_youtube", { label: test.uploaded.variant ?? "–" })}
            </a>
          ) : (
            <button className="btn btn-primary" onClick={() => onUpload(`ab:${pick}`)} disabled={!test.files_ok}>
              <Icon name="upload" />
              {t("ab.upload_pick", { label: pick })}
            </button>
          )}
        </>
      }
    >
      <div className="ab-dialog">
        {test.stale && (
          <div className="notice notice-warn">
            <Icon name="alert" />
            <span>{t("ab.stale")}</span>
          </div>
        )}
        <div className="ab-grid">
          {(["A", "B"] as const).map((label) => {
            const v = test.variants[label];
            const win = test.winner === label;
            return (
              <section key={label} className={`ab-card${win ? " ab-win" : ""}`} aria-label={`${label} · ${t(`ab.style.${v.style}`)}`}>
                <div className="ab-head">
                  <span className="ab-label mono">{label}</span>
                  <span className="ab-style">{t(`ab.style.${v.style}`)}</span>
                  {win && (
                    <span className="chip chip-gold">
                      <Icon name="sparkles" size={11} />
                      {t("ab.predicted")}
                    </span>
                  )}
                  <span className="ab-score mono" title={t("ab.score_hint")}>
                    {num(Math.round(v.score))}
                  </span>
                </div>
                <video
                  src={urls.hookVariant(projectId, cand.id, label, v.rendered_at)}
                  controls
                  playsInline
                  preload="metadata"
                />
                {v.hook_text && (
                  <p className="ab-hook" dir="auto">
                    “{v.hook_text}”
                  </p>
                )}
                <ul className="ab-reasons">
                  {v.reasons.slice(0, 6).map((r) => (
                    <li key={r.code}>
                      <span>{reasonText(r, t, num)}</span>
                      <span className={`mono ${r.points >= 0 ? "ok-text" : "danger-text"}`}>
                        {r.points >= 0 ? "+" : "−"}
                        {num(Math.abs(Math.round(r.points)))}
                      </span>
                    </li>
                  ))}
                </ul>
                {v.judge?.why && (
                  <p className="muted ab-why" dir="auto">
                    <Icon name="sparkles" size={11} /> {v.judge.why}
                  </p>
                )}
              </section>
            );
          })}
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 12.5 }}>
          {test.upload_pick.how === "bandit"
            ? t("ab.pick_bandit", { label: pick })
            : t("ab.pick_pretest", { label: pick, margin: num(Math.round(test.margin)) })}
        </p>
        <RealTestNote realTest={realTest} />
      </div>
    </Modal>
  );
}

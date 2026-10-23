import { useState } from "react";
import { api, type Candidate, type ProjectDetail } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { CopyButton } from "./ui";
import { Icon } from "./Icons";

// ----------------------------------------------------------------- signals

export function SignalStats({ cand, project }: { cand: Candidate | null; project: ProjectDetail }) {
  const { t, num } = useI18n();
  const signals = project.highlights?.signals ?? {};
  const order = Object.keys(signals).filter((k) => signals[k].status === "ok");
  const keywords = cand
    ? [...new Set(cand.reasons.filter((r) => r.code === "keyword" && r.value).map((r) => r.value!))]
    : [];
  return (
    <section className="panel" aria-labelledby="sig-title">
      <div className="panel-head">
        <h2 className="section-title" id="sig-title">
          {t("signals.title")}
        </h2>
        {cand && <span className="chip chip-outline mono">#{String(cand.rank).padStart(2, "0")}</span>}
      </div>
      {cand ? (
        <>
          <div className="sig-list">
            {order.map((name) => {
              const v = cand.signal_scores[name] ?? 0;
              return (
                <div className="sig" key={name}>
                  <div className="sig-top">
                    <span>{t(`signal.${name}`)}</span>
                    <span className="val">{num(Math.round(v * 100))}</span>
                  </div>
                  <div className="sig-bar">
                    <span className={v >= 0.6 ? "hot" : ""} style={{ width: `${Math.max(2, v * 100)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="divider" />
          <dl className="kv">
            <dt>{t("signals.score")}</dt>
            <dd className="mono gold">{num(cand.hype_score)}/100</dd>
            <dt>{t("signals.peak")}</dt>
            <dd className="tc">{fmtTime(cand.peak)}</dd>
            <dt>{t("signals.length")}</dt>
            <dd className="tc">{num(Math.round(cand.duration))} s</dd>
          </dl>
          {keywords.length > 0 && (
            <>
              <div className="divider" />
              <div style={{ display: "grid", gap: 8 }}>
                <span className="muted" style={{ fontSize: 12.5 }}>
                  {t("signals.keywords")}
                </span>
                <div className="cand-reasons">
                  {keywords.map((k) => (
                    <span key={k} className="chip" dir="auto">
                      “{k}”
                    </span>
                  ))}
                </div>
              </div>
            </>
          )}
        </>
      ) : (
        <p className="muted">—</p>
      )}
    </section>
  );
}

// ----------------------------------------------------------------- publish

function ScoreRing({ score, label }: { score: number | null; label: string | null }) {
  const { t, num } = useI18n();
  const r = 50;
  const c = 2 * Math.PI * r;
  const frac = score == null ? 0 : score / 100;
  return (
    <div style={{ display: "grid", gap: 8, justifyItems: "center" }}>
      <div className="score-ring" role="img" aria-label={`${t("publish.viral")}: ${score ?? "—"}/100`}>
        <svg viewBox="0 0 116 116">
          <circle cx="58" cy="58" r={r} fill="none" stroke="var(--track)" strokeWidth="8" />
          {score != null && (
            <circle cx="58" cy="58" r={r} fill="none" stroke="var(--gold)" strokeWidth="8" strokeLinecap="round"
              strokeDasharray={`${c * frac} ${c}`} />
          )}
        </svg>
        <div className="center">
          <span className="num">{score == null ? "—" : num(score)}</span>
          <span className="den">/100</span>
        </div>
      </div>
      {label ? (
        <span className="chip chip-gold">{t(`publish.label.${label}`)}</span>
      ) : (
        <span className="muted" style={{ fontSize: 12 }}>{t("publish.viral")}</span>
      )}
    </div>
  );
}

export function PublishPanel({ cand, projectId }: { cand: Candidate | null; projectId: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const pub = cand?.publish;
  const ready = !!pub?.available;

  const regenerate = async () => {
    if (!cand) return;
    setBusy(true);
    try {
      await api.regeneratePublish(projectId, cand.id);
    } catch {
      toast({ kind: "info", text: t("publish.soon") });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-labelledby="pub-title">
      <div className="panel-head">
        <h2 className="section-title" id="pub-title">
          {t("publish.title")}
        </h2>
        {!ready && (
          <span className="soon">
            <Icon name="sparkles" size={12} />
            {t("publish.soon")}
          </span>
        )}
      </div>
      <div className="pub-grid">
        <ScoreRing score={ready ? pub!.viral_score : null} label={ready ? pub!.viral_label : null} />
        <div style={{ minWidth: 0 }}>
          <div className="pub-block">
            <div className="pub-row">
              <span className="field-label">{t("publish.titles")}</span>
              <button className="btn btn-sm btn-ghost" disabled={!ready || busy} onClick={regenerate}>
                <Icon name="refresh" />
                {t("publish.new")}
              </button>
            </div>
            {ready && pub!.titles.length ? (
              pub!.titles.map((title) => (
                <div className="sugg" key={title}>
                  <span dir="auto">{title}</span>
                  <CopyButton text={title} />
                </div>
              ))
            ) : (
              [92, 74, 84].map((w) => (
                <div className="sugg" key={w} aria-hidden="true">
                  <span>
                    <span className="skeleton" style={{ display: "block", height: 10, width: `${w}%` }} />
                  </span>
                  <button className="btn btn-sm btn-ghost icon-btn" disabled tabIndex={-1}>
                    <Icon name="copy" />
                  </button>
                </div>
              ))
            )}
          </div>
          <div className="pub-block">
            <div className="pub-row">
              <span className="field-label">{t("publish.hashtags")}</span>
              {ready && pub!.hashtags.length ? (
                <CopyButton text={pub!.hashtags.join(" ")} label={t("common.copy_all")} />
              ) : (
                <button className="btn btn-sm btn-ghost" disabled>
                  <Icon name="copy" />
                  {t("common.copy_all")}
                </button>
              )}
            </div>
            <div className="cand-reasons">
              {ready && pub!.hashtags.length
                ? pub!.hashtags.map((h) => (
                    <span key={h} className="chip" dir="auto">
                      {h}
                    </span>
                  ))
                : [54, 72, 46, 64].map((w) => (
                    <span key={w} className="skeleton" style={{ width: w, height: 22 }} aria-hidden="true" />
                  ))}
            </div>
          </div>
          <div className="pub-block">
            <div className="pub-row">
              <span className="field-label">{t("publish.cover")}</span>
              {ready && pub!.cover_prompt ? (
                <CopyButton text={pub!.cover_prompt} />
              ) : (
                <button className="btn btn-sm btn-ghost icon-btn" disabled aria-label={t("common.copy")}>
                  <Icon name="copy" />
                </button>
              )}
            </div>
            {ready && pub!.cover_prompt ? (
              <div className="prompt-box" dir="auto">
                {pub!.cover_prompt}
              </div>
            ) : (
              <div className="prompt-box" aria-hidden="true" style={{ display: "grid", gap: 7 }}>
                <span className="skeleton" style={{ height: 9, width: "96%" }} />
                <span className="skeleton" style={{ height: 9, width: "88%" }} />
                <span className="skeleton" style={{ height: 9, width: "60%" }} />
              </div>
            )}
          </div>
        </div>
      </div>
      {!ready && <p className="pub-soon-note">{t("publish.soon_note")}</p>}
    </section>
  );
}

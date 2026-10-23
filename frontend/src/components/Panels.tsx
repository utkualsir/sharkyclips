import { api, type Candidate, type Job, type ProjectDetail } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { CopyButton, jobLabel } from "./ui";
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

const SUBS = ["hook", "retention", "trend_fit", "length_fit"] as const;

export function PublishPanel({
  cand,
  projectId,
  llmAvailable,
  llmJob,
}: {
  cand: Candidate | null;
  projectId: string;
  llmAvailable: boolean;
  llmJob: Job | null;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const pub = cand?.publish;
  const ready = !!pub?.available;
  const working = !!llmJob;
  const writingTitles = llmJob?.kind === "titles" && llmJob.params?.clip_id === cand?.id;

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const skeletonTitles = [92, 74, 84].map((w) => (
    <div className="sugg" key={w} aria-hidden="true">
      <span>
        <span className="skeleton" style={{ display: "block", height: 10, width: `${w}%` }} />
      </span>
      <button className="btn btn-sm btn-ghost icon-btn" disabled tabIndex={-1}>
        <Icon name="copy" />
      </button>
    </div>
  ));

  return (
    <section className="panel" aria-labelledby="pub-title">
      <div className="panel-head">
        <h2 className="section-title" id="pub-title">
          {t("publish.title")}
        </h2>
        {ready ? (
          <span className="chip chip-outline" title={pub?.language ?? ""}>
            <Icon name="sparkles" size={12} />
            {t("publish.by_ai")}
          </span>
        ) : !llmAvailable ? (
          <span className="soon">
            <Icon name="sparkles" size={12} />
            {t("publish.soon")}
          </span>
        ) : null}
      </div>

      {working && !writingTitles && (
        <div className="notice" style={{ marginBottom: 14 }}>
          <span className="spinner" />
          <span>{jobLabel(llmJob!, t, num)}</span>
        </div>
      )}

      <div className="pub-grid">
        <div style={{ display: "grid", gap: 14, justifyItems: "center", alignContent: "start" }}>
          <ScoreRing score={ready ? pub!.viral_score : null} label={ready ? pub!.viral_label : null} />
          {ready && pub!.sub_scores && (
            <div className="sig-list" style={{ width: "100%", gap: 8 }}>
              {SUBS.map((k) => (
                <div className="sig" key={k} style={{ gap: 4 }}>
                  <div className="sig-top" style={{ fontSize: 11.5 }}>
                    <span className="muted">{t(`publish.sub.${k}`)}</span>
                    <span className="val">{num(pub!.sub_scores![k])}</span>
                  </div>
                  <div className="sig-bar" style={{ height: 4 }}>
                    <span style={{ width: `${Math.max(2, pub!.sub_scores![k])}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ minWidth: 0 }}>
          {ready && cand?.llm?.what_happens && (
            <p className="muted" style={{ margin: "0 0 12px", fontSize: 12.5, lineHeight: 1.5 }} lang="en" dir="ltr">
              {cand.llm.what_happens}
            </p>
          )}
          <div className="pub-block">
            <div className="pub-row">
              <span className="field-label">{t("publish.titles")}</span>
              <button
                className="btn btn-sm btn-ghost"
                disabled={!ready || working}
                onClick={() => cand && run(() => api.regeneratePublish(projectId, cand.id))}
              >
                {writingTitles ? <span className="spinner" style={{ width: 13, height: 13 }} /> : <Icon name="refresh" />}
                {t("publish.new")}
              </button>
            </div>
            {ready && pub!.titles.length
              ? pub!.titles.map((title) => (
                  <div className="sugg" key={title} style={writingTitles ? { opacity: 0.5 } : undefined}>
                    <span dir="auto">{title}</span>
                    <CopyButton text={title} />
                  </div>
                ))
              : skeletonTitles}
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
              <div className="prompt-box" dir="ltr" lang="en">
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
      {!ready && !llmAvailable && <p className="pub-soon-note">{t("publish.no_llm")}</p>}
      {!ready && llmAvailable && !working && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14, flexWrap: "wrap" }}>
          <button className="btn btn-primary btn-sm" onClick={() => run(() => api.analyze(projectId))}>
            <Icon name="sparkles" />
            {t("publish.analyze")}
          </button>
          <span className="muted" style={{ fontSize: 12.5 }}>
            {t("publish.analyze_note")}
          </span>
        </div>
      )}
    </section>
  );
}

import { useEffect, useState } from "react";
import { api, type Candidate, type ChatStats, type Job, type ProjectDetail } from "../api";
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
          {project.chat?.status === "ok" && cand.chat && <ChatSection chat={cand.chat} clipStart={cand.start} />}
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

/** "5.2x" from the chat signal -> "5,2×" in the UI language's number format. */
export function fmtRatio(value: string, num: (n: number, digits?: number) => string): string {
  const x = parseFloat(value);
  return Number.isFinite(x) ? `${num(x, 1)}×` : value;
}

function ChatSection({ chat, clipStart }: { chat: ChatStats; clipStart: number }) {
  const { t, num } = useI18n();
  const hot = chat.ratio != null && chat.ratio >= 2;
  return (
    <>
      <div className="divider" />
      <div className="chat-stats">
        <span className="field-label chat-head">
          <Icon name="message" size={13} />
          {t("chat.title")}
        </span>
        {chat.messages === 0 ? (
          <span className="muted" style={{ fontSize: 12.5 }}>
            {t("chat.quiet")}
          </span>
        ) : (
          <>
            <dl className="kv">
              <dt>{t("chat.messages")}</dt>
              <dd className="mono">{num(chat.messages)}</dd>
              <dt>{t("chat.people")}</dt>
              <dd className="mono">{num(chat.authors)}</dd>
              <dt>{t("chat.per_minute")}</dt>
              <dd>
                <span className="mono">{num(chat.per_minute, 1)}</span>
                {chat.ratio != null && (
                  <span className={hot ? "gold" : "muted"} style={{ fontSize: 12 }}>
                    {" · "}
                    {t("chat.vs_usual", { x: num(chat.ratio, 1) })}
                  </span>
                )}
              </dd>
            </dl>
          </>
        )}
        {(chat.spikes.length > 0 || chat.reactions.length > 0) && (
          <div className="cand-reasons">
            {chat.spikes.map((s) => (
              <span key={`s${s.t}`} className="chip chip-gold">
                {t("reason.chat_spike")}
                {s.value && (
                  <span className="mono" dir="ltr">
                    {" "}
                    {t("chat.spike_at", { value: fmtRatio(s.value, num), time: fmtTime(Math.max(0, s.t - clipStart)) })}
                  </span>
                )}
              </span>
            ))}
            {chat.reactions.map((r) => (
              <span key={`r${r}`} className="chip" title={t("reason.chat_reactions")} dir="auto">
                {t("chat.reactions")}: “{r}”
              </span>
            ))}
          </div>
        )}
      </div>
    </>
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
  const [votes, setVotes] = useState<Record<string, number>>({});
  useEffect(() => setVotes(pub?.title_votes ?? {}), [cand?.id, pub?.title_votes]);

  const vote = async (title: string, v: 1 | -1) => {
    if (!cand) return;
    const next = votes[title] === v ? 0 : v;
    const before = votes;
    setVotes({ ...votes, [title]: next });
    try {
      await api.voteTitle(projectId, cand.id, title, next as -1 | 0 | 1);
      if (next) toast({ kind: "ok", text: t("publish.vote_saved") });
    } catch (e: any) {
      setVotes(before);
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

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
                    <button
                      type="button"
                      className={`btn btn-sm btn-ghost icon-btn vote vote-up`}
                      aria-pressed={votes[title] === 1}
                      aria-label={t("publish.like")}
                      title={t("publish.like")}
                      onClick={() => vote(title, 1)}
                    >
                      <Icon name="thumb-up" size={14} />
                    </button>
                    <button
                      type="button"
                      className={`btn btn-sm btn-ghost icon-btn vote vote-down`}
                      aria-pressed={votes[title] === -1}
                      aria-label={t("publish.dislike")}
                      title={t("publish.dislike")}
                      onClick={() => vote(title, -1)}
                    >
                      <Icon name="thumb-down" size={14} />
                    </button>
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

import { useEffect, useMemo, useRef, useState } from "react";
import { api, urls, type Candidate, type MontageExport, type ProjectDetail } from "../api";
import { Icon } from "../components/Icons";
import { CopyButton, JobLine, Toggle } from "../components/ui";
import { fmtBytes, fmtTime } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useMeta } from "../meta";
import { href } from "../router";
import { useToast } from "../toast";

// Same timings as backend/sharkyclips/montage.py (for the length estimate).
const XFADE = 0.5;
const CARD_S = 1.8;
const INTRO_S = 3.2;
const OUTRO_S = 3.4;
const DEFAULT_N = 8;
const MAX_CLIPS = 30;

/** Calibrated score when the channel is calibrated, else the default viral score, else hype. */
export function clipScore(c: Candidate): number {
  return c.publish.calibrated?.score ?? c.publish.viral_score ?? c.hype_score;
}

function defaultPick(cands: Candidate[], accepted: string[], n: number): string[] {
  const acc = cands.filter((c) => accepted.includes(c.id));
  const pool = acc.length >= 2 ? acc : cands;
  return [...pool].sort((a, b) => clipScore(b) - clipScore(a)).slice(0, n).map((c) => c.id);
}

function ExportCard({ projectId, ex, onDelete }: { projectId: string; ex: MontageExport; onDelete: () => void }) {
  const { t, num, relTime } = useI18n();
  const all = [ex.description, ex.chapters_text].filter(Boolean).join("\n\n");
  return (
    <article className="card export-card">
      <div className="export-media">
        <video src={urls.export(projectId, ex.name)} poster={urls.exportPoster(projectId, ex.name)} controls preload="none" />
      </div>
      <div className="export-body">
        <div className="export-head">
          <div>
            <h3 className="export-title" dir="auto">
              {ex.titles[0] ?? ex.name}
            </h3>
            <div className="muted export-meta">
              <span className="tc">{fmtTime(ex.duration)}</span> · {num(ex.items.length)} {t("bestof.clips_short")} ·{" "}
              {ex.width}×{ex.height} {ex.fps} fps · {fmtBytes(ex.size_bytes)} · {ex.encoder} · {relTime(ex.created_at)}
            </div>
          </div>
          <div className="export-actions">
            <a className="btn btn-sm" href={urls.exportDownload(projectId, ex.name)} download>
              <Icon name="download" />
              {t("common.download")}
            </a>
            <button className="btn btn-sm btn-ghost icon-btn" onClick={onDelete} aria-label={t("bestof.delete")} title={t("bestof.delete")}>
              <Icon name="trash" />
            </button>
          </div>
        </div>

        <div className="pub-block">
          <div className="pub-row">
            <span className="field-label">{t("bestof.title_options")}</span>
            {!ex.model && <span className="muted" style={{ fontSize: 12 }}>{t("bestof.no_llm_texts")}</span>}
          </div>
          {ex.titles.map((title) => (
            <div className="sugg" key={title}>
              <span dir="auto">{title}</span>
              <CopyButton text={title} />
            </div>
          ))}
        </div>

        {ex.description && (
          <div className="pub-block">
            <div className="pub-row">
              <span className="field-label">{t("bestof.description")}</span>
              <CopyButton text={ex.description} label={t("common.copy")} />
            </div>
            <div className="prompt-box export-text" dir="auto">
              {ex.description}
            </div>
          </div>
        )}

        <div className="pub-block">
          <div className="pub-row">
            <span className="field-label">{t("bestof.chapters")}</span>
            <div style={{ display: "flex", gap: 4 }}>
              <CopyButton text={ex.chapters_text} label={t("common.copy")} />
              {ex.description && <CopyButton text={all} label={t("bestof.copy_both")} />}
            </div>
          </div>
          <div className="prompt-box export-text mono" dir="auto">
            {ex.chapters_text}
          </div>
          <p className="muted" style={{ fontSize: 12, margin: "6px 0 0" }}>
            {t("bestof.chapters_note")}
          </p>
        </div>
      </div>
    </article>
  );
}

export default function BestOf({ id }: { id: string }) {
  const { t, num } = useI18n();
  const meta = useMeta();
  const toast = useToast();
  const { jobs, lastFinished, finishedTick } = useJobs();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [order, setOrder] = useState<string[]>([]);
  const [n, setN] = useState(DEFAULT_N);
  const [intro, setIntro] = useState(true);
  const [outro, setOutro] = useState(true);
  const [cards, setCards] = useState(true);
  const [lang, setLang] = useState<string | null>(null);
  const [exports, setExports] = useState<MontageExport[]>([]);
  const [drag, setDrag] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const inited = useRef(false);

  const loadExports = () => api.exports(id).then(setExports).catch(() => {});

  useEffect(() => {
    api.project(id).then((p) => {
      setProject(p);
      setLang((l) => l ?? p.output_language);
      if (!inited.current && p.highlights) {
        inited.current = true;
        const cands = p.highlights.candidates;
        const acc = p.review.accepted.filter((x) => cands.some((c) => c.id === x));
        const start = Math.min(DEFAULT_N, Math.max(acc.length >= 2 ? acc.length : 5, 2));
        setN(start);
        setOrder(defaultPick(cands, p.review.accepted, start));
      }
    });
    loadExports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (lastFinished?.kind === "montage" && lastFinished.project_id === id) {
      loadExports();
      if (lastFinished.status === "done") toast({ kind: "ok", text: t("bestof.done") });
      if (lastFinished.status === "error" && lastFinished.error)
        toast({ kind: "err", text: lastFinished.error.message, hint: lastFinished.error.hint });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishedTick]);

  const cands = project?.highlights?.candidates ?? [];
  const byId = useMemo(() => new Map(cands.map((c) => [c.id, c])), [cands]);
  const chosen = order.map((x) => byId.get(x)).filter(Boolean) as Candidate[];
  const rest = cands.filter((c) => !order.includes(c.id)).sort((a, b) => clipScore(b) - clipScore(a));
  const montageJobs = jobs.filter((j) => j.kind === "montage" && j.project_id === id && isActive(j));
  const calibrated = !!project?.calibration.calibrated;

  const pieces = chosen.length * (cards ? 2 : 1) + (intro ? 1 : 0) + (outro ? 1 : 0);
  const total =
    chosen.reduce((a, c) => a + c.duration, 0) +
    (cards ? chosen.length * CARD_S : 0) +
    (intro ? INTRO_S : 0) +
    (outro ? OUTRO_S : 0) -
    Math.max(0, pieces - 1) * XFADE;

  const moveTo = (cid: string, to: number) => {
    const next = order.filter((x) => x !== cid);
    next.splice(Math.max(0, Math.min(to, next.length)), 0, cid);
    setOrder(next);
  };

  const pickTop = () => project && setOrder(defaultPick(cands, project.review.accepted, n));

  const submit = async () => {
    try {
      await api.montage(id, { clip_ids: order, intro, outro, cards, lang: lang ?? undefined });
      toast({ kind: "ok", text: t("bestof.queued"), action: { label: t("nav.queue"), run: () => (window.location.hash = href.queue) } });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const remove = async (ex: MontageExport) => {
    if (!window.confirm(t("bestof.delete_confirm"))) return;
    await api.deleteExport(id, ex.name);
    loadExports();
  };

  if (!project) {
    return (
      <main className="page">
        <div className="skeleton" style={{ height: 40, width: 380, marginBottom: 24 }} />
        <div className="skeleton" style={{ height: 420, borderRadius: 16 }} />
      </main>
    );
  }

  return (
    <main className="page bestof-page">
      <a className="crumbs" href={href.project(id)}>
        <Icon name="chevron-left" className="icon flip-rtl" />
        <span dir="auto">{project.title}</span>
      </a>
      <div className="page-head">
        <div>
          <h1 className="display">{t("bestof.title")}</h1>
          <p className="lede">{t("bestof.lede")}</p>
        </div>
      </div>

      {!project.highlights ? (
        <div className="empty">
          <h2 className="display">{t("project.no_highlights_title")}</h2>
        </div>
      ) : (
        <div className="bestof-layout">
          <section className="card bestof-list" aria-labelledby="bo-order">
            <div className="q-section-head">
              <h2 className="section-title" id="bo-order">
                {t("bestof.order")} <span className="count mono">{chosen.length}</span>
              </h2>
              <div className="bo-topn">
                <label htmlFor="bo-n" className="muted">
                  {t("bestof.top_n")}
                </label>
                <input
                  id="bo-n"
                  className="input"
                  type="number"
                  min={2}
                  max={Math.min(MAX_CLIPS, cands.length)}
                  value={n}
                  onChange={(e) => setN(Math.max(2, Math.min(MAX_CLIPS, Number(e.target.value) || 2)))}
                />
                <button className="btn btn-sm" onClick={pickTop}>
                  <Icon name="sparkles" />
                  {t("bestof.pick_top")}
                </button>
              </div>
            </div>
            <p className="muted bo-note">
              {calibrated ? t("bestof.sorted_calibrated") : t("bestof.sorted_default")}
            </p>
            {chosen.length === 0 ? (
              <p className="muted">{t("bestof.empty")}</p>
            ) : (
              <ol className="bo-items">
                {chosen.map((c, i) => (
                  <li
                    key={c.id}
                    className={`bo-item${drag === c.id ? " dragging" : ""}${over === c.id ? " drag-over" : ""}`}
                    draggable
                    data-clip={c.id}
                    onDragStart={(e) => {
                      setDrag(c.id);
                      e.dataTransfer.effectAllowed = "move";
                      e.dataTransfer.setData("text/plain", c.id);
                    }}
                    onDragEnd={() => {
                      setDrag(null);
                      setOver(null);
                    }}
                    onDragOver={(e) => {
                      if (!drag || drag === c.id) return;
                      e.preventDefault();
                      setOver(c.id);
                    }}
                    onDragLeave={() => setOver((o) => (o === c.id ? null : o))}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (drag) moveTo(drag, i);
                      setDrag(null);
                      setOver(null);
                    }}
                  >
                    <span className="bo-grip" aria-hidden="true">
                      <Icon name="grip" />
                    </span>
                    <span className="bo-pos mono">{String(i + 1).padStart(2, "0")}</span>
                    <img className="bo-thumb" src={urls.frame(id, c.peak, 640)} alt="" loading="lazy" draggable={false} />
                    <div className="bo-main">
                      <div className="bo-title" dir="auto">
                        {c.publish.titles[0] || c.text}
                      </div>
                      <div className="muted bo-meta">
                        #{String(c.rank).padStart(2, "0")} · <span className="tc">{fmtTime(c.start)}</span> ·{" "}
                        {num(Math.round(c.duration))} s
                        {project.review.accepted.includes(c.id) && <> · <span className="ok-text">{t("bestof.accepted")}</span></>}
                      </div>
                    </div>
                    <span className="bo-score mono" title={t("publish.viral")}>
                      <Icon name="sparkles" size={12} />
                      {num(clipScore(c))}
                    </span>
                    <div className="bo-actions">
                      <button className="btn btn-sm btn-ghost icon-btn" disabled={i === 0} onClick={() => moveTo(c.id, i - 1)} aria-label={t("queue.up")}>
                        <Icon name="chevron-up" />
                      </button>
                      <button
                        className="btn btn-sm btn-ghost icon-btn"
                        disabled={i === chosen.length - 1}
                        onClick={() => moveTo(c.id, i + 1)}
                        aria-label={t("queue.down")}
                      >
                        <Icon name="chevron-down" />
                      </button>
                      <button className="btn btn-sm btn-ghost icon-btn" onClick={() => setOrder(order.filter((x) => x !== c.id))} aria-label={t("bestof.remove")} title={t("bestof.remove")}>
                        <Icon name="x" />
                      </button>
                    </div>
                  </li>
                ))}
              </ol>
            )}

            {rest.length > 0 && (
              <details className="bo-more">
                <summary>{t("bestof.add_more", { n: rest.length })}</summary>
                <ul className="bo-rest">
                  {rest.map((c) => (
                    <li key={c.id}>
                      <button
                        className="bo-add"
                        disabled={order.length >= MAX_CLIPS}
                        onClick={() => setOrder([...order, c.id])}
                      >
                        <Icon name="plus" size={14} />
                        <span className="mono">#{String(c.rank).padStart(2, "0")}</span>
                        <span className="bo-title" dir="auto">
                          {c.publish.titles[0] || c.text}
                        </span>
                        <span className="mono muted">{num(clipScore(c))}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>

          <aside className="card bestof-side">
            <h2 className="section-title">{t("bestof.options")}</h2>
            <div className="toggle-line">
              <Toggle checked={intro} onChange={setIntro} label={t("bestof.intro")} />
              <span>{t("bestof.intro")}</span>
            </div>
            <div className="toggle-line">
              <Toggle checked={cards} onChange={setCards} label={t("bestof.cards")} />
              <span>{t("bestof.cards")}</span>
            </div>
            <div className="toggle-line">
              <Toggle checked={outro} onChange={setOutro} label={t("bestof.outro")} />
              <span>{t("bestof.outro")}</span>
            </div>
            <div>
              <label className="field-label" htmlFor="bo-lang" style={{ display: "block", marginBottom: 6 }}>
                {t("bestof.language")}
              </label>
              <select id="bo-lang" className="select" value={lang ?? ""} onChange={(e) => setLang(e.target.value)}>
                {UI_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>
            <dl className="kv bo-summary">
              <dt>{t("bestof.length")}</dt>
              <dd className="tc">{chosen.length >= 2 ? fmtTime(total) : "–"}</dd>
              <dt>{t("bestof.format")}</dt>
              <dd className="mono">1920×1080 · 60 fps</dd>
              <dt>{t("bestof.loudness")}</dt>
              <dd className="mono">−14 LUFS</dd>
            </dl>
            <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
              {meta?.llm.available ? t("bestof.llm_note") : t("bestof.no_llm_note")}
            </p>
            {montageJobs.length > 0 ? (
              <div style={{ display: "grid", gap: 10 }}>
                {montageJobs.map((j) => (
                  <JobLine key={j.id} job={j} onCancel={() => api.cancelJob(j.id)} />
                ))}
                <a className="btn btn-sm btn-ghost" href={href.queue}>
                  {t("bestof.see_queue")}
                </a>
              </div>
            ) : (
              <button className="btn btn-primary btn-lg btn-block" disabled={chosen.length < 2} onClick={submit}>
                <Icon name="layers" />
                {chosen.length >= 2 ? t("bestof.make", { n: chosen.length }) : t("bestof.need_more")}
              </button>
            )}
          </aside>
        </div>
      )}

      {exports.length > 0 && (
        <section className="q-section" aria-labelledby="bo-exports">
          <div className="q-section-head">
            <h2 className="section-title" id="bo-exports">
              {t("bestof.exports")} <span className="count mono">{exports.length}</span>
            </h2>
          </div>
          <div className="exports">
            {exports.map((ex) => (
              <ExportCard key={ex.name} projectId={id} ex={ex} onDelete={() => remove(ex)} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

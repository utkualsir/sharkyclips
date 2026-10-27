import { useCallback, useEffect, useMemo, useState } from "react";
import { api, urls, type ProjectDetail, type StoriesView, type Story } from "../api";
import { Icon } from "../components/Icons";
import { CopyButton, JobLine, Toggle } from "../components/ui";
import { fmtBytes, fmtTime } from "../format";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { href } from "../router";
import { useToast } from "../toast";

// Story clips (1.2.5): 2-4 moments from across the stream as one 30-60 s Short.
// Same timings as backend/sharkyclips/story.py (for the live length while editing).
const TRANSITION = 0.25;
const CARD_S = 0.9;

function storyLength(s: Story, cards: boolean): number {
  const pieces = s.segments.map((x) => x.end - x.start);
  const nCards = s.segments.filter((x, k) => k > 0 && cards && x.card).length;
  return pieces.reduce((a, b) => a + b, 0) + nCards * CARD_S - (pieces.length + nCards - 1) * TRANSITION;
}

function StoryCard({
  projectId,
  story,
  project,
  rendering,
  onChanged,
}: {
  projectId: string;
  story: Story;
  project: ProjectDetail;
  rendering: ReturnType<typeof useJobs>["jobs"][number] | undefined;
  onChanged: () => void;
}) {
  const { t, num, relTime } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const cands = project.highlights?.candidates ?? [];
  const pub = story.publish;
  const total = storyLength(story, story.cards);

  const save = async (body: Parameters<typeof api.updateStory>[2]) => {
    setBusy(true);
    try {
      await api.updateStory(projectId, story.id, body);
      onChanged();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const order = story.segments.map((s) => s.cid);
  const move = (i: number, dir: -1 | 1) => {
    const next = [...order];
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    save({ segments: next.map((cid) => ({ cid, card: story.segments.find((s) => s.cid === cid)?.card ?? "" })) });
  };
  const remove = (cid: string) =>
    save({ segments: story.segments.filter((s) => s.cid !== cid).map((s) => ({ cid: s.cid, card: s.card })) });
  const render = async () => {
    try {
      await api.renderStory(projectId, story.id);
      toast({ kind: "ok", text: t("story.render_queued") });
      onChanged();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const del = async () => {
    if (!window.confirm(t("story.delete_confirm"))) return;
    await api.deleteStory(projectId, story.id).catch(() => {});
    onChanged();
  };
  const allPub = pub
    ? [pub.titles[0] ?? "", "", pub.description, "", pub.hashtags.join(" ")].join("\n").trim()
    : "";

  return (
    <article className="card story-card" data-story={story.id}>
      <div className="story-head">
        <div style={{ minWidth: 0 }}>
          <div className="story-chips">
            <span className="chip chip-gold">{t(`story.arc.${story.arc}`)}</span>
            <span className="chip chip-outline tc">{fmtTime(total)}</span>
            <span className="chip chip-outline">{t("story.n_moments", { n: story.segments.length })}</span>
          </div>
          <h2 className="story-title" dir="auto">
            {story.title}
          </h2>
          {story.pitch && (
            <p className="muted story-pitch" dir="auto">
              {story.pitch}
            </p>
          )}
        </div>
        <button className="btn btn-sm btn-ghost icon-btn" onClick={del} aria-label={t("story.delete")} title={t("story.delete")}>
          <Icon name="trash" />
        </button>
      </div>

      <ol className="story-segs">
        {story.segments.map((s, i) => {
          const c = cands.find((x) => x.id === s.cid);
          const text = story.cut_text.find((x) => x.cid === s.cid)?.text ?? "";
          return (
            <li key={s.cid} className="story-seg">
              {i > 0 && story.cards && s.card && (
                <div className="story-cardtext">
                  <Icon name="file" size={12} /> {s.card}
                </div>
              )}
              <div className="story-seg-row">
                <img className="story-thumb" src={urls.frame(projectId, s.start + Math.min(2, (s.end - s.start) / 2), 320)} alt="" loading="lazy" />
                <div className="story-seg-body">
                  <div className="story-seg-meta">
                    <a href={href.project(projectId)} className="tc">
                      #{String(c?.rank ?? s.rank ?? 0).padStart(2, "0")}
                    </a>
                    <span className="tc">
                      {fmtTime(s.start)} – {fmtTime(s.end)} · {num(Math.round(s.end - s.start))} s
                    </span>
                    {s.role && <span className="chip chip-outline">{s.role}</span>}
                  </div>
                  <p className="story-seg-text" dir="auto">
                    {c?.llm?.what_happens || text}
                  </p>
                </div>
                <div className="story-seg-actions">
                  <button className="btn btn-sm btn-ghost icon-btn" disabled={busy || i === 0} onClick={() => move(i, -1)} aria-label={t("story.up")} title={t("story.up")}>
                    <Icon name="arrow-up" />
                  </button>
                  <button
                    className="btn btn-sm btn-ghost icon-btn"
                    disabled={busy || i === story.segments.length - 1}
                    onClick={() => move(i, 1)}
                    aria-label={t("story.down")}
                    title={t("story.down")}
                  >
                    <Icon name="arrow-down" />
                  </button>
                  <button
                    className="btn btn-sm btn-ghost icon-btn"
                    disabled={busy || story.segments.length <= 2}
                    onClick={() => remove(s.cid)}
                    aria-label={t("story.remove")}
                    title={story.segments.length <= 2 ? t("story.remove_min") : t("story.remove")}
                  >
                    <Icon name="x" />
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="story-controls">
        <label className="edit-line">
          <Toggle checked={story.cards} onChange={(v) => save({ cards: v })} label={t("story.cards")} />
          <span>{t("story.cards")}</span>
        </label>
        <span style={{ flex: 1 }} />
        {rendering ? (
          <div style={{ minWidth: 260 }}>
            <JobLine job={rendering} onCancel={() => api.cancelJob(rendering.id)} />
          </div>
        ) : (
          <button className="btn btn-primary" onClick={render} disabled={busy}>
            <Icon name="film" />
            {story.render ? t("story.render_again") : t("story.render")}
          </button>
        )}
      </div>

      {story.render && (
        <div className="story-result">
          <video src={urls.story(projectId, story.id, story.render.rendered_at)} controls playsInline preload="metadata" />
          <div className="story-result-body">
            <div className="muted" style={{ fontSize: 12.5 }}>
              {t("story.rendered", { when: relTime(story.render.rendered_at) })} · {fmtTime(story.render.info.duration)} ·{" "}
              {fmtBytes(story.render.size_bytes)} · {num(story.render.info.lufs, 1)} LUFS
            </div>
            <a className="btn btn-sm" href={urls.story(projectId, story.id, story.render.rendered_at, true)} download>
              <Icon name="download" />
              {t("common.download")}
            </a>
          </div>
        </div>
      )}

      <details className="story-details">
        <summary>{t("story.cut_text")}</summary>
        <p className="muted" style={{ fontSize: 12.5, margin: "6px 0" }}>
          {t("story.cut_text_hint")}
        </p>
        <ol className="story-transcript">
          {story.cut_text.map((x) => (
            <li key={x.cid} dir="auto">
              {x.card && story.cards && <b>[{x.card}] </b>}
              {x.text || "…"}
            </li>
          ))}
        </ol>
      </details>

      {pub && (
        <details className="story-details" open>
          <summary>
            {t("story.publish")}
            {pub.source === "clips" && <span className="muted"> · {t("story.publish_from_clips")}</span>}
          </summary>
          <div className="story-pub">
            <div className="field-label">{t("publish.titles")}</div>
            <ul className="story-titles">
              {pub.titles.map((x) => (
                <li key={x} dir="auto">
                  <span>{x}</span>
                  <CopyButton text={x} />
                </li>
              ))}
            </ul>
            {pub.description && (
              <>
                <div className="field-label">{t("yt.description")}</div>
                <p className="story-desc" dir="auto">
                  {pub.description}
                </p>
              </>
            )}
            {pub.hashtags.length > 0 && (
              <p className="mono" style={{ fontSize: 12.5 }} dir="auto">
                {pub.hashtags.join(" ")}
              </p>
            )}
            {pub.cover_prompt && (
              <>
                <div className="field-label">{t("story.cover_prompt")}</div>
                <p className="muted story-desc" dir="auto">
                  {pub.cover_prompt}
                </p>
              </>
            )}
            <div className="edit-line">
              <CopyButton text={allPub} label={t("common.copy_all")} />
              {pub.cover_prompt && <CopyButton text={pub.cover_prompt} label={t("story.copy_cover")} />}
            </div>
          </div>
        </details>
      )}
    </article>
  );
}

export default function Stories({ id }: { id: string }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const { jobs, finishedTick } = useJobs();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [data, setData] = useState<StoriesView | null>(null);

  const load = useCallback(() => {
    api.project(id).then(setProject).catch(() => {});
    api.stories(id).then(setData).catch(() => {});
  }, [id]);
  useEffect(load, [load, finishedTick]);

  const active = jobs.filter((j) => j.project_id === id && isActive(j));
  const proposing = active.find((j) => j.kind === "story");
  const renders = useMemo(() => new Map(active.filter((j) => j.kind === "story_render").map((j) => [j.params?.story_id, j])), [active]);

  const propose = async () => {
    try {
      await api.proposeStories(id, project?.output_language);
      load();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  return (
    <main className="page stories-page">
      <div className="page-head">
        <div style={{ minWidth: 0 }}>
          <a className="crumbs" href={href.project(id)}>
            <Icon name="chevron-left" className="icon flip-rtl" />
            {project?.title ?? t("nav.library")}
          </a>
          <h1 className="display">{t("story.title")}</h1>
          <p className="lede">{t("story.lede", { min: num(data?.limits.min ?? 30), max: num(data?.limits.max ?? 60) })}</p>
        </div>
        <button className="btn btn-gold" onClick={propose} disabled={!!proposing || !project?.highlights}>
          <Icon name="sparkles" />
          {data?.stories.length ? t("story.propose_again") : t("story.propose")}
        </button>
      </div>

      {proposing && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <JobLine job={proposing} onCancel={() => api.cancelJob(proposing.id)} />
        </div>
      )}
      {data && !data.llm && (
        <div className="notice" style={{ marginBottom: 16 }}>
          <Icon name="alert" />
          <span>{t("story.no_llm")}</span>
        </div>
      )}

      {!data || !project ? (
        <div className="skeleton" style={{ height: 320, borderRadius: 16 }} />
      ) : data.stories.length === 0 ? (
        <div className="empty">
          <Icon name="book" size={28} />
          <h2 className="display">{data.reason ? t(`story.reason.${data.reason}`, { n: data.good ?? 0 }) : t("story.empty_title")}</h2>
          <p style={{ margin: 0, maxWidth: "52ch" }}>
            {data.reason === "no_arc" && data.none_reason ? data.none_reason : data.reason ? t(`story.reason_hint.${data.reason}`) : t("story.empty_body")}
          </p>
        </div>
      ) : (
        <div className="story-list">
          {data.stories.map((s) => (
            <StoryCard key={s.id} projectId={id} story={s} project={project} rendering={renders.get(s.id)} onChanged={load} />
          ))}
        </div>
      )}
    </main>
  );
}

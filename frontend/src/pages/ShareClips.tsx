// 1.2.66 "Share clips": every clip of a project in one big grid, a clear status on each card,
// pick many (or one), choose the platforms once, see the summary, Publish. The daily upload limit
// decides what goes today; the rest is planned for the next days by the server.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, urls } from "../api";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { TARGET_NAME, type Target } from "../multipost";
import { href } from "../router";
import { shareApi, shareChanged, whenText, type Batch, type ShareBoard, type ShareCard, type ShareKind } from "../share";
import { useToast } from "../toast";
import { Icon } from "../components/Icons";
import { PlatformIcon } from "../components/PlatformIcons";
import { ProgressBar } from "../components/ui";
import { ShareFlow } from "../components/ShareFlow";
import { UploadsLeft } from "../components/UploadsLeft";

type Filter = "all" | "not_shared" | "shared";
const ORDER: Target[] = ["youtube", "reels", "tiktok"];
const UNDO_MS = 8000;

/** Cards that count as "shared" for the filter and the dimming: out on at least one platform. */
const isShared = (c: ShareCard) => c.status.shared.length > 0;

export default function ShareClips({ id }: { id: string }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [board, setBoard] = useState<ShareBoard | null>(null);
  const [missing, setMissing] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [sel, setSel] = useState<string[]>([]);
  const [flow, setFlow] = useState<string[] | null>(null);
  const [playing, setPlaying] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, number>>({}); // cid -> undo timer
  const pendingRef = useRef(pending);
  pendingRef.current = pending;

  const load = useCallback(() => {
    shareApi
      .board(id)
      .then(setBoard)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setMissing(true);
      });
  }, [id]);
  useEffect(() => load(), [load]);
  // the top bar's "left today" pill follows the board's count
  const leftNow = board?.limit.left;
  useEffect(() => {
    if (leftNow != null) shareChanged();
  }, [leftNow]);

  const moving =
    !!board &&
    (board.batch?.state === "running" || board.clips.some((c) => c.status.kind === "working"));
  useEffect(() => {
    const iv = window.setInterval(() => document.visibilityState === "visible" && load(), moving ? 2000 : 15000);
    return () => window.clearInterval(iv);
  }, [load, moving]);

  // unschedule waits UNDO_MS with Undo; leaving the page sends it at once
  const commitUnschedule = useCallback(
    (cids: string[]) => {
      shareApi
        .unschedule(id, cids)
        .then((r) => {
          if (r.errors.length) toast({ kind: "err", text: r.errors[0].message });
          shareChanged();
          load();
        })
        .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
    },
    [id, load, toast],
  );
  useEffect(
    () => () => {
      const left = Object.keys(pendingRef.current);
      for (const tm of Object.values(pendingRef.current)) window.clearTimeout(tm);
      if (left.length) shareApi.unschedule(id, left).then(shareChanged).catch(() => {});
    },
    [id],
  );
  const unschedule = (cids: string[]) => {
    const tm = window.setTimeout(() => {
      setPending((p) => {
        const n = { ...p };
        for (const c of cids) delete n[c];
        return n;
      });
      commitUnschedule(cids);
    }, UNDO_MS);
    setPending((p) => ({ ...p, ...Object.fromEntries(cids.map((c) => [c, tm])) }));
    toast({
      kind: "info",
      text: t("share.unscheduled", { n: cids.length }),
      hint: t("share.undo_hint"),
      ms: UNDO_MS,
      action: {
        label: t("share.undo"),
        run: () => {
          window.clearTimeout(tm);
          setPending((p) => {
            const n = { ...p };
            for (const c of cids) delete n[c];
            return n;
          });
        },
      },
    });
  };

  const retry = (cids: string[]) =>
    shareApi
      .retry(id, cids)
      .then((r) => {
        if (r.errors.length) toast({ kind: "err", text: r.errors[0].message, hint: r.errors[0].hint });
        else toast({ kind: "ok", text: t("share.retrying", { n: cids.length }) });
        load();
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));

  const clips = useMemo(() => board?.clips ?? [], [board]);
  const counts = useMemo(
    () => ({
      all: clips.length,
      not_shared: clips.filter((c) => !isShared(c)).length,
      shared: clips.filter(isShared).length,
    }),
    [clips],
  );
  const shown = clips.filter((c) => (filter === "all" ? true : filter === "shared" ? isShared(c) : !isShared(c)));
  const toggle = (cid: string) => setSel((s) => (s.includes(cid) ? s.filter((x) => x !== cid) : [...s, cid]));
  const notShared = clips.filter((c) => c.status.kind === "not_shared").map((c) => c.id);

  // keyboard: Esc clears the selection, Ctrl+A picks every clip shown
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (flow || document.querySelector('[aria-modal="true"]')) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable)) {
        if (!(el.tagName === "INPUT" && (el as HTMLInputElement).type === "checkbox")) return;
      }
      if (e.key === "Escape" && sel.length) {
        e.preventDefault();
        setSel([]);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        e.preventDefault();
        setSel(shown.map((c) => c.id));
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  if (missing) {
    return (
      <main className="page">
        <div className="empty">
          <h1 className="display">{t("project.not_found")}</h1>
          <a className="btn" href={href.library}>
            {t("nav.library")}
          </a>
        </div>
      </main>
    );
  }
  if (!board) {
    return (
      <main className="page">
        <div className="empty">
          <span className="spinner" />
        </div>
      </main>
    );
  }

  const selCards = clips.filter((c) => sel.includes(c.id));
  const left = board.limit.left;
  const batch = board.batch && !board.batch.dismissed ? board.batch : null;

  return (
    <main className="page share-page">
      <a className="crumbs" href={href.project(id)}>
        <Icon name="chevron-left" className="icon flip-rtl" />
        <span dir="auto">{board.title}</span>
      </a>
      <div className="share-head">
        <div style={{ minWidth: 0 }}>
          <h1 className="display">{t("share.title")}</h1>
          <p className="muted share-lede">{t("share.lede")}</p>
        </div>
        <UploadsLeft value={board.limit} big />
      </div>

      {batch && <BatchPanel pid={id} batch={batch} clips={clips} onChanged={load} onUnschedule={unschedule} />}

      <div className="share-toolbar">
        <div className="share-tabs" role="group" aria-label={t("share.filter")}>
          {(["all", "not_shared", "shared"] as Filter[]).map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {t(`share.filter_${f}`)} <span className="share-count mono">{num(counts[f])}</span>
            </button>
          ))}
        </div>
        <div className="share-selbtns">
          <button type="button" className="btn" onClick={() => setSel(shown.map((c) => c.id))} disabled={!shown.length}>
            <Icon name="check" /> {t("share.select_all")}
          </button>
          <button type="button" className="btn" onClick={() => setSel(notShared)} disabled={!notShared.length}>
            <Icon name="list" /> {t("share.select_not_shared")}
          </button>
          {sel.length > 0 && (
            <button type="button" className="btn btn-ghost" onClick={() => setSel([])}>
              <Icon name="x" /> {t("share.clear")}
            </button>
          )}
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="empty share-empty">
          <Icon name="film" size={28} />
          <p style={{ margin: 0 }}>{clips.length ? t("share.none_here") : t("share.no_clips")}</p>
        </div>
      ) : (
        <ul className="share-grid" aria-label={t("share.title")}>
          {shown.map((c) => (
            <Tile
              key={c.id}
              pid={id}
              c={c}
              selected={sel.includes(c.id)}
              onSelect={() => toggle(c.id)}
              playing={playing === c.id}
              onPlay={(on) => setPlaying((p) => (on ? c.id : p === c.id ? null : p))}
              pending={c.id in pending}
              onShare={() => setFlow([c.id])}
              onRetry={() => retry([c.id])}
              onUnschedule={() => unschedule([c.id])}
            />
          ))}
        </ul>
      )}

      <div className={`share-bar${sel.length ? " is-on" : ""}`} role="region" aria-label={t("share.selection")}>
        {sel.length > 0 && (
          <>
            <div className="share-bar-text">
              <b>{t("share.selected", { n: sel.length })}</b>
              <span className="muted">
                {sel.length > left
                  ? t("share.bar_rollover", { today: num(Math.min(left, sel.length)), later: num(sel.length - left) })
                  : t("share.bar_fits", { n: num(sel.length), left: num(left) })}
              </span>
            </div>
            <button type="button" className="btn btn-ghost" onClick={() => setSel([])}>
              {t("share.clear")}
            </button>
            <button type="button" className="btn btn-primary btn-lg share-go" onClick={() => setFlow(selCards.map((c) => c.id))}>
              <Icon name="upload" /> {t("share.share_selected", { n: num(sel.length) })}
            </button>
          </>
        )}
      </div>

      {flow && (
        <ShareFlow
          pid={id}
          board={board}
          clipIds={flow}
          onClose={() => setFlow(null)}
          onStarted={() => {
            setFlow(null);
            setSel([]);
            shareChanged();
            load();
          }}
        />
      )}
    </main>
  );
}

// ---------------------------------------------------------------- one card

const KIND_ICON: Record<ShareKind, string> = {
  not_shared: "upload",
  scheduled: "calendar",
  working: "refresh",
  shared: "check",
  failed: "alert",
};

function Tile({
  pid,
  c,
  selected,
  onSelect,
  playing,
  onPlay,
  pending,
  onShare,
  onRetry,
  onUnschedule,
}: {
  pid: string;
  c: ShareCard;
  selected: boolean;
  onSelect: () => void;
  playing: boolean;
  onPlay: (on: boolean) => void;
  pending: boolean;
  onShare: () => void;
  onRetry: () => void;
  onUnschedule: () => void;
}) {
  const { t, lang, num } = useI18n();
  const vid = useRef<HTMLVideoElement>(null);
  const hover = useRef<number | null>(null);
  const [sound, setSound] = useState(false);
  const s = c.status;
  const kind: ShareKind = pending ? "not_shared" : s.kind;
  const shared = isShared(c);
  const src =
    c.video.kind === "clip" ? urls.clip(pid, c.id, c.video.stamp) : `${urls.source(pid)}#t=${c.start.toFixed(2)},${c.end.toFixed(2)}`;
  const titleId = `sh-t-${c.id}`;

  useEffect(() => {
    const v = vid.current;
    if (!v) return;
    if (playing) {
      v.muted = !sound;
      if (c.video.kind === "source" && (v.currentTime < c.start || v.currentTime > c.end)) v.currentTime = c.start;
      v.play().catch(() => {});
    } else {
      v.pause();
    }
  }, [playing, sound, c.start, c.end, c.video.kind]);

  const onTime = () => {
    const v = vid.current;
    if (v && c.video.kind === "source" && v.currentTime >= c.end) v.currentTime = c.start; // loop the clip only
  };
  const enter = () => {
    if (window.matchMedia("(hover: none)").matches) return;
    hover.current = window.setTimeout(() => onPlay(true), 350);
  };
  const leave = () => {
    if (hover.current) window.clearTimeout(hover.current);
    if (!sound) onPlay(false);
  };

  let label: string;
  if (kind === "shared") label = t("share.kind_shared");
  else if (kind === "scheduled")
    label = s.next_at
      ? t("share.kind_scheduled_at", { when: whenText(s.next_at, lang) })
      : s.planned.some((x) => x.by_hand)
        ? t("share.kind_by_hand")
        : t("share.kind_scheduled");
  else if (kind === "working") label = t("share.kind_working");
  else if (kind === "failed") label = t("share.kind_failed");
  else label = t("share.kind_not_shared");

  return (
    <li
      className={`sh-card kind-${kind}${selected ? " is-selected" : ""}${shared ? " is-shared" : ""}`}
      aria-labelledby={titleId}
    >
      <div className="sh-media" onMouseEnter={enter} onMouseLeave={leave}>
        {playing ? (
          <video
            ref={vid}
            src={src}
            className="sh-video"
            playsInline
            loop={c.video.kind === "clip"}
            muted={!sound}
            preload="metadata"
            onTimeUpdate={onTime}
            aria-label={c.title}
          />
        ) : (
          <img className="sh-thumb" src={urls.frame(pid, c.peak, 640)} alt="" loading="lazy" decoding="async" />
        )}
        <label className="sh-check">
          <input type="checkbox" checked={selected} onChange={onSelect} aria-label={t("share.select_clip", { title: c.title })} />
          <span aria-hidden="true" />
        </label>
        {c.viral_score != null && (
          <span className="sh-score mono" title={t("share.score")}>
            <Icon name="zap" size={12} />
            {num(Math.round(c.viral_score))}
          </span>
        )}
        <button
          type="button"
          className="sh-play"
          onClick={() => {
            if (playing && sound) {
              setSound(false);
              onPlay(false);
            } else {
              setSound(true);
              onPlay(true);
            }
          }}
          aria-label={playing && sound ? t("share.pause") : t("share.play", { title: c.title })}
          aria-pressed={playing && sound}
        >
          <Icon name={playing && sound ? "pause" : "play"} size={22} />
        </button>
        <span className="sh-dur mono">{fmtTime(c.duration)}</span>
      </div>

      <div className="sh-body">
        <h2 className="sh-title" id={titleId} dir="auto">
          {c.title}
        </h2>
        <div className={`sh-badge badge-${kind}`}>
          <Icon name={KIND_ICON[kind]} size={13} />
          <span>{label}</span>
          {kind === "working" && s.progress != null && <span className="mono">{num(Math.round(s.progress * 100))}%</span>}
        </div>
        {(s.shared.length > 0 || s.planned.length > 0 || s.failed.length > 0 || s.busy.length > 0) && !pending && (
          <ul className="sh-plats" aria-label={t("share.where_now")}>
            {ORDER.map((p) => {
              const out = s.shared.find((x) => x.platform === p);
              const plan = s.planned.find((x) => x.platform === p);
              const bad = s.failed.find((x) => x.platform === p);
              const busy = s.busy.includes(p);
              if (!out && !plan && !bad && !busy) return null;
              const what = out
                ? t("share.p_out")
                : bad
                  ? t("share.p_failed")
                  : busy
                    ? t("share.p_busy")
                    : plan?.at
                      ? whenText(plan.at, lang)
                      : t("share.p_by_hand");
              return (
                <li key={p} className={out ? "is-out" : bad ? "is-bad" : ""}>
                  <PlatformIcon p={p} size={15} />
                  {out?.url ? (
                    <a href={out.url} target="_blank" rel="noreferrer" title={t("share.open_post", { name: TARGET_NAME[p] })}>
                      {TARGET_NAME[p]} <Icon name="link" size={11} />
                    </a>
                  ) : (
                    <span>{TARGET_NAME[p]}</span>
                  )}
                  <span className="muted">{what}</span>
                </li>
              );
            })}
          </ul>
        )}
        {kind === "failed" && s.failed[0]?.message && (
          <p className="sh-error" dir="auto">
            {s.failed[0].message}
          </p>
        )}
        {kind === "working" && <ProgressBar value={s.progress} label={label} />}
        <div className="sh-actions">
          {kind === "failed" && (
            <button type="button" className="btn btn-primary" onClick={onRetry}>
              <Icon name="refresh" /> {t("share.retry")}
            </button>
          )}
          {kind === "scheduled" && (
            <button type="button" className="btn" onClick={onUnschedule}>
              <Icon name="x" /> {t("share.unschedule")}
            </button>
          )}
          {kind !== "working" && kind !== "failed" && (
            <button
              type="button"
              className={`btn${kind === "not_shared" ? " btn-primary" : ""}`}
              onClick={onShare}
              aria-describedby={titleId}
            >
              <Icon name="upload" /> {shared || kind === "scheduled" ? t("share.share_more") : t("share.share")}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------- the batch progress panel

function BatchPanel({
  pid,
  batch,
  clips,
  onChanged,
  onUnschedule,
}: {
  pid: string;
  batch: Batch;
  clips: ShareCard[];
  onChanged: () => void;
  onUnschedule: (cids: string[]) => void;
}) {
  const { t, lang, num } = useI18n();
  const [open, setOpen] = useState(true);
  const by = new Map(clips.map((c) => [c.id, c]));
  const rows = batch.rows;
  const done = rows.filter((r) => r.state === "done" || r.state === "failed").length;
  const running = batch.state === "running";
  const cancelable = rows.filter((r) => {
    const k = by.get(r.clip_id)?.status.kind;
    return k === "scheduled" || k === "working";
  });
  return (
    <section className={`share-batch${running ? " is-running" : ""}`} aria-label={t("share.batch_title")}>
      <div className="share-batch-head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <h2 className="share-batch-title">
            {running ? t("share.batch_running") : batch.state === "stopped" ? t("share.batch_stopped") : t("share.batch_done")}
          </h2>
          <span className="muted mono">{t("share.batch_count", { done: num(done), n: num(rows.length) })}</span>
        </div>
        {cancelable.length > 0 && (
          <button type="button" className="btn" onClick={() => onUnschedule(cancelable.map((r) => r.clip_id))}>
            <Icon name="x" /> {t("share.batch_cancel")}
          </button>
        )}
        <button type="button" className="btn btn-ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          <Icon name={open ? "chevron-up" : "chevron-down"} /> {open ? t("share.hide") : t("share.show")}
        </button>
        {!running && (
          <button
            type="button"
            className="btn btn-ghost icon-btn"
            aria-label={t("common.close")}
            onClick={() => shareApi.dismiss(pid).then(onChanged).catch(() => {})}
          >
            <Icon name="x" />
          </button>
        )}
      </div>
      <ProgressBar value={rows.length ? done / rows.length : null} label={t("share.batch_title")} />
      {open && (
        <ol className="share-batch-rows">
          {rows.map((r) => {
            const card = by.get(r.clip_id);
            const posts = card?.posts;
            return (
              <li key={r.clip_id} className={`br-${r.state}`}>
                <span className="br-state" aria-hidden="true">
                  {r.state === "done" ? <Icon name="check" size={14} /> : r.state === "failed" ? <Icon name="alert" size={14} /> : r.state === "starting" ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <Icon name="clock" size={14} />}
                </span>
                <span className="br-title" dir="auto">
                  {r.title}
                </span>
                <span className="br-plats">
                  {r.platforms.map((p) => {
                    const st = posts?.[p];
                    const status = st?.status ?? "idle";
                    const txt =
                      status === "published"
                        ? t("share.p_out")
                        : status === "failed"
                          ? t("share.p_failed")
                          : ["preparing", "uploading", "processing"].includes(status)
                            ? t("share.p_busy")
                            : status === "ready"
                              ? st?.remind_at && new Date(st.remind_at).getTime() > Date.now()
                                ? whenText(st.remind_at, lang)
                                : t("share.p_by_hand")
                              : st?.publish_at
                                ? whenText(st.publish_at, lang)
                                : r.state === "queued"
                                  ? t("share.p_waiting")
                                  : r.when === "now"
                                    ? t("share.now")
                                    : whenText(r.when, lang);
                    return (
                      <span key={p} className={`br-plat st-${status}`}>
                        <PlatformIcon p={p} size={14} />
                        <span className="visually-hidden">{TARGET_NAME[p]}: </span>
                        {txt}
                      </span>
                    );
                  })}
                </span>
                {r.state === "failed" && r.error?.message && (
                  <span className="br-error" dir="auto">
                    {r.error.message}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

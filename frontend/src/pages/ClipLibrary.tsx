import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, urls, type LibraryRow, type LibraryView, type LibStatus } from "../api";
import { Icon } from "../components/Icons";
import { LockBanner, PublishSetupDialog, RescheduleDialog, ScheduleDialog, useWhen } from "../components/PublishTools";
import { CopyButton, Modal, ProgressBar, Segmented } from "../components/ui";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { useJobs } from "../jobs";
import { go, href } from "../router";
import { useToast } from "../toast";

type Tab = "all" | LibStatus;
const TABS: Tab[] = ["all", "draft", "scheduled", "published", "failed", "locked"];

function dayKey(d: Date) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function startOfWeek(d: Date) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const wd = (x.getDay() + 6) % 7; // Monday first
  x.setDate(x.getDate() - wd);
  return x;
}

function addDays(d: Date, n: number) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

// ------------------------------------------------------------------ one row

function StatusPill({ row }: { row: LibraryRow }) {
  const { t } = useI18n();
  const cls = { draft: "", scheduled: "chip-gold", published: "chip-success", failed: "chip-danger", locked: "chip-danger" }[row.status];
  return (
    <span className={`chip ${cls}`}>
      {row.status === "locked" && <Icon name="lock" size={12} />}
      {t(`pub.status.${row.status}`)}
    </span>
  );
}

function StepLine({ row }: { row: LibraryRow }) {
  const { t, relTime, num } = useI18n();
  const when = useWhen();
  if (row.status === "scheduled") {
    const due = row.publish_at ?? row.date;
    return (
      <div className="lib-step">
        {due && (
          <span>
            <Icon name="clock" size={12} /> {when.full(due)} · <b>{relTime(due)}</b>
          </span>
        )}
        <span className={row.step === "uploaded" ? "ok-text" : "muted"}>
          {row.step === "uploaded" ? <Icon name="check" size={12} /> : null} {t(`pub.step.${row.step ?? "waiting"}`)}
          {row.job?.progress != null && row.step === "uploading" && <> {num(Math.round(row.job.progress * 100))}%</>}
          {row.job?.paused && <> · {t("pub.paused")}</>}
          {row.step === "retrying" && row.next_try_at && <> · {t("pub.retry_at", { when: when.time(row.next_try_at) })}</>}
        </span>
        {row.moved_from && <span className="muted">{t("pub.moved_from", { when: when.full(row.moved_from) })}</span>}
        {row.job && row.job.progress != null && <ProgressBar value={row.job.progress} />}
      </div>
    );
  }
  if (row.status === "published" || row.status === "locked") {
    const u = row.upload;
    return (
      <div className="lib-step">
        {row.date && (
          <span>
            {when.full(row.date)} · {relTime(row.date)}
          </span>
        )}
        {u && (u.views != null || u.likes != null) && (
          <span className="mono">
            <Icon name="eye" size={12} /> {num(u.views ?? 0)} · <Icon name="thumb-up" size={12} /> {u.likes != null ? num(u.likes) : "–"}
          </span>
        )}
        {u && <span className="muted">{t(`yt.privacy.${u.privacy}`)}</span>}
        {row.step === "checking" && <span className="muted">{t("pub.step.checking")}</span>}
        {row.status === "locked" && <span className="warn-text">{t("pub.locked_row")}</span>}
      </div>
    );
  }
  if (row.status === "failed" && row.error) {
    return (
      <div className="lib-step">
        <span className="err-text" dir="auto">
          <Icon name="alert" size={12} /> {row.error.message}
        </span>
        {row.error.hint && <span className="muted" dir="auto">{row.error.hint}</span>}
      </div>
    );
  }
  return null;
}

function RowActions({
  row,
  onEdit,
  onSchedule,
  onReschedule,
  onChanged,
}: {
  row: LibraryRow;
  onEdit: () => void;
  onSchedule: () => void;
  onReschedule: () => void;
  onChanged: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const act = (fn: () => Promise<unknown>, ok?: string) =>
    fn()
      .then(() => {
        if (ok) toast({ kind: "ok", text: ok });
        onChanged();
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  const future = !!row.publish_at && new Date(row.publish_at).getTime() > Date.now();
  const canNow = row.status === "draft" || (row.status === "scheduled" && (!row.upload || future));
  const fix = row.error?.fix;
  return (
    <div className="lib-actions">
      {row.status === "failed" && fix && fix !== "wait" && (
        fix === "reconnect" ? (
          <a className="btn btn-sm btn-primary" href={`${href.settings}`}>
            <Icon name="link" />
            {t("pub.fix.reconnect")}
          </a>
        ) : fix === "edit" ? (
          <button className="btn btn-sm btn-primary" onClick={onEdit}>
            {t("pub.fix.edit")}
          </button>
        ) : (
          <button className="btn btn-sm btn-primary" onClick={() => act(() => api.retryPublish(row.project_id, row.clip_id), t("pub.retrying"))}>
            <Icon name="refresh" />
            {t(`pub.fix.${fix}`)}
          </button>
        )
      )}
      {row.status === "draft" && (
        <button className="btn btn-sm" onClick={onSchedule}>
          <Icon name="calendar" />
          {t("pub.schedule")}
        </button>
      )}
      {row.status === "scheduled" && (
        <button className="btn btn-sm btn-ghost" onClick={onReschedule}>
          <Icon name="calendar" />
          {t("pub.reschedule")}
        </button>
      )}
      {canNow && (
        <button className="btn btn-sm btn-ghost" onClick={() => act(() => api.publishNow(row.project_id, row.clip_id), t("pub.now_queued"))}>
          <Icon name="upload" />
          {t("pub.publish_now")}
        </button>
      )}
      <button className="btn btn-sm btn-ghost icon-btn" onClick={onEdit} aria-label={t("pub.edit")} title={t("pub.edit")}>
        <Icon name="settings" />
      </button>
      {(row.status === "scheduled" || (row.status === "failed" && row.planned)) && (
        <button className="btn btn-sm btn-ghost icon-btn" onClick={() => setConfirm(true)} aria-label={t("pub.cancel")} title={t("pub.cancel")}>
          <Icon name="x" />
        </button>
      )}
      {row.upload && (
        <>
          <a className="btn btn-sm btn-ghost icon-btn" href={row.upload.url} target="_blank" rel="noreferrer" aria-label={t("pub.open_youtube")} title={t("pub.open_youtube")}>
            <Icon name="link" />
          </a>
          <CopyButton text={row.upload.url} label={undefined} />
        </>
      )}
      {confirm && (
        <Modal
          top
          title={t("pub.cancel_title")}
          onClose={() => setConfirm(false)}
          footer={
            <>
              <button className="btn" onClick={() => setConfirm(false)}>
                {t("common.back")}
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  setConfirm(false);
                  act(() => api.cancelPublish(row.project_id, row.clip_id), t("pub.cancelled"));
                }}
              >
                {t("pub.cancel")}
              </button>
            </>
          }
        >
          <p style={{ margin: 0 }}>{row.upload ? t("pub.cancel_body_uploaded") : t("pub.cancel_body")}</p>
        </Modal>
      )}
    </div>
  );
}

function Row({
  row,
  selected,
  onSelect,
  ...rest
}: {
  row: LibraryRow;
  selected: boolean;
  onSelect: (v: boolean) => void;
  onEdit: () => void;
  onSchedule: () => void;
  onReschedule: () => void;
  onChanged: () => void;
}) {
  const { t, num } = useI18n();
  const [img, setImg] = useState(true);
  const selectable = !row.upload;
  return (
    <li className={`lib-row${selected ? " selected" : ""}`}>
      <span className="lib-check">
        {selectable && (
          <input type="checkbox" checked={selected} onChange={(e) => onSelect(e.target.checked)} aria-label={t("pub.select", { title: row.title })} />
        )}
      </span>
      <span className="lib-thumb">
        {img ? <img src={urls.clipThumb(row.project_id, row.clip_id)} alt="" loading="lazy" onError={() => setImg(false)} /> : <Icon name="film" size={20} />}
      </span>
      <div className="lib-main">
        <div className="lib-title" dir="auto">
          {row.title}
        </div>
        <div className="lib-meta muted">
          <a href={href.project(row.project_id)}>{row.project_title}</a>
          <span>#{row.rank}</span>
          <span className="mono">{fmtTime(row.duration)}</span>
          {row.viral_score != null && (
            <span className="chip chip-outline" title={t("pub.viral")}>
              <Icon name="sparkles" size={11} /> {num(row.viral_score)}
            </span>
          )}
          <StatusPill row={row} />
        </div>
        <StepLine row={row} />
      </div>
      <RowActions row={row} {...rest} />
    </li>
  );
}

// ------------------------------------------------------------------ calendar

function Calendar({
  rows,
  limit,
  onOpen,
  onChanged,
}: {
  rows: LibraryRow[];
  limit: number;
  onOpen: (row: LibraryRow) => void;
  onChanged: () => void;
}) {
  const { t, lang, num } = useI18n();
  const when = useWhen();
  const toast = useToast();
  const [mode, setMode] = useState<"week" | "month">(() => {
    try {
      return localStorage.getItem("sc-lib-cal") === "month" ? "month" : "week";
    } catch {
      return "week";
    }
  });
  const [anchor, setAnchor] = useState(() => new Date());
  const [over, setOver] = useState<string | null>(null);
  const drag = useRef<LibraryRow | null>(null);
  useEffect(() => {
    try {
      localStorage.setItem("sc-lib-cal", mode);
    } catch {
      /* ignore */
    }
  }, [mode]);

  const byDay = useMemo(() => {
    const m = new Map<string, LibraryRow[]>();
    for (const r of rows) {
      if (!r.date || !["scheduled", "published", "locked"].includes(r.status)) continue;
      const k = dayKey(new Date(r.date));
      m.set(k, [...(m.get(k) ?? []), r].sort((a, b) => (a.date ?? "").localeCompare(b.date ?? "")));
    }
    return m;
  }, [rows]);

  const days: Date[] = useMemo(() => {
    if (mode === "week") {
      const s = startOfWeek(anchor);
      return Array.from({ length: 7 }, (_, i) => addDays(s, i));
    }
    const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
    const s = startOfWeek(first);
    return Array.from({ length: 42 }, (_, i) => addDays(s, i));
  }, [mode, anchor]);

  const today = dayKey(new Date());
  const fmtHead = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, mode === "week" ? { day: "numeric", month: "short", year: "numeric" } : { month: "long", year: "numeric" });
  const fmtDay = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, { weekday: "short", day: "numeric" });
  const fmtWd = new Intl.DateTimeFormat(`${lang}-u-nu-latn`, { weekday: "short" });
  const move = (n: number) => setAnchor(mode === "week" ? addDays(anchor, 7 * n) : new Date(anchor.getFullYear(), anchor.getMonth() + n, 1));

  const drop = async (day: Date) => {
    const r = drag.current;
    drag.current = null;
    setOver(null);
    if (!r || !r.publish_at) return;
    const old = new Date(r.publish_at);
    const target = new Date(day.getFullYear(), day.getMonth(), day.getDate(), old.getHours(), old.getMinutes());
    if (dayKey(target) === dayKey(old)) return;
    try {
      const res = await api.reschedule(r.project_id, r.clip_id, target.toISOString(), true);
      toast({ kind: "ok", text: t("pub.scheduled_for", { when: when.full(res.publish_at) }) });
      onChanged();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const draggable = (r: LibraryRow) => r.status === "scheduled" && !!r.publish_at && new Date(r.publish_at).getTime() > Date.now();

  return (
    <section className="card lib-cal" aria-label={t("pub.calendar")}>
      <div className="lib-cal-head">
        <div className="inline-row">
          <button className="btn btn-sm btn-ghost icon-btn" onClick={() => move(-1)} aria-label={t("pub.cal_prev")}>
            <Icon name="chevron-left" />
          </button>
          <button className="btn btn-sm" onClick={() => setAnchor(new Date())}>
            {t("pub.cal_today")}
          </button>
          <button className="btn btn-sm btn-ghost icon-btn" onClick={() => move(1)} aria-label={t("pub.cal_next")}>
            <Icon name="chevron-right" />
          </button>
          <h2 className="section-title" style={{ margin: 0 }}>
            {fmtHead.format(mode === "week" ? days[0] : anchor)}
          </h2>
        </div>
        <span className="muted">{t("pub.cal_limit", { n: limit })}</span>
        <Segmented<"week" | "month">
          value={mode}
          options={[
            { value: "week", label: t("pub.cal_week") },
            { value: "month", label: t("pub.cal_month") },
          ]}
          onChange={setMode}
          label={t("pub.calendar")}
        />
      </div>
      {mode === "month" && (
        <div className="lib-cal-wd" aria-hidden="true">
          {days.slice(0, 7).map((d) => (
            <span key={d.toISOString()}>{fmtWd.format(d)}</span>
          ))}
        </div>
      )}
      <div className={`lib-cal-grid ${mode}`}>
        {days.map((d) => {
          const k = dayKey(d);
          const items = byDay.get(k) ?? [];
          const count = items.length;
          const past = d.getTime() < new Date(new Date().toDateString()).getTime();
          const out = mode === "month" && d.getMonth() !== anchor.getMonth();
          const shown = mode === "month" ? items.slice(0, 3) : items;
          return (
            <div
              key={k}
              className={`lib-day${k === today ? " today" : ""}${past ? " past" : ""}${out ? " out" : ""}${count >= limit ? " full" : ""}${over === k ? " over" : ""}`}
              onDragOver={(e) => {
                if (!past && drag.current) {
                  e.preventDefault();
                  setOver(k);
                }
              }}
              onDragLeave={() => setOver((o) => (o === k ? null : o))}
              onDrop={(e) => {
                e.preventDefault();
                drop(d);
              }}
            >
              <div className="lib-day-head">
                <span>{mode === "week" ? fmtDay.format(d) : d.getDate()}</span>
                <span className={`mono lib-day-count${count >= limit ? " full" : ""}`} title={t("pub.cal_day_count", { n: count, limit })}>
                  {num(count)}/{num(limit)}
                </span>
              </div>
              {shown.map((r) => (
                <button
                  key={r.key}
                  className={`lib-chip s-${r.status}`}
                  draggable={draggable(r)}
                  onDragStart={(e) => {
                    drag.current = r;
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("text/plain", r.key);
                  }}
                  onDragEnd={() => {
                    drag.current = null;
                    setOver(null);
                  }}
                  onClick={() => onOpen(r)}
                  title={`${r.title} · ${r.project_title}`}
                >
                  <span className="mono">{r.date ? when.time(r.date) : ""}</span>
                  <span className="lib-chip-title" dir="auto">
                    {r.title}
                  </span>
                </button>
              ))}
              {items.length > shown.length && <span className="muted lib-more">+{num(items.length - shown.length)}</span>}
            </div>
          );
        })}
      </div>
      <p className="field-hint">{t("pub.cal_hint")}</p>
    </section>
  );
}

// ------------------------------------------------------------------ page

export default function ClipLibrary({ view }: { view: "list" | "calendar" }) {
  const { t, num, relTime } = useI18n();
  const toast = useToast();
  const { jobs } = useJobs();
  const [data, setData] = useState<LibraryView | null>(null);
  const [failed, setFailed] = useState(false);
  const [tab, setTab] = useState<Tab>("all");
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [setup, setSetup] = useState<LibraryRow | null>(null);
  const [plan, setPlan] = useState<LibraryRow[] | null>(null);
  const [resched, setResched] = useState<LibraryRow | null>(null);

  const load = useCallback(() => {
    api
      .library()
      .then((d) => {
        setData(d);
        setFailed(false);
      })
      .catch((e) => {
        setFailed(true);
        toast({ kind: "err", text: e.message, hint: e.hint });
      });
  }, [toast]);

  useEffect(load, [load]);
  // live: follow the publish jobs (render / upload progress) and the clock (countdowns)
  const jobSig = jobs
    .filter((j) => (j.params as any)?.plan_key || j.kind === "upload" || j.kind === "yt_stats")
    .map((j) => `${j.id}:${j.status}:${Math.round((j.progress ?? 0) * 20)}`)
    .join(",");
  useEffect(() => {
    const id = window.setTimeout(load, 400);
    return () => window.clearTimeout(id);
  }, [jobSig, load]);
  useEffect(() => {
    const id = window.setInterval(load, 30_000);
    return () => window.clearInterval(id);
  }, [load]);

  const rows = data?.rows ?? [];
  const shown = tab === "all" ? rows : rows.filter((r) => r.status === tab);
  const selRows = rows.filter((r) => sel.has(r.key));
  const toggle = (k: string, v: boolean) => {
    const next = new Set(sel);
    if (v) next.add(k);
    else next.delete(k);
    setSel(next);
  };
  const selectable = shown.filter((r) => !r.upload);
  const allOn = selectable.length > 0 && selectable.every((r) => sel.has(r.key));

  return (
    <main className="page lib-page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("pub.title")}</h1>
          <p className="lede">{t("pub.lede")}</p>
        </div>
        {data && (
          <div className="lib-summary card">
            <div>
              <span className="muted">{t("pub.quota_today")}</span>
              <b className="mono">{data.youtube.connected ? num(data.quota.uploads_left) : "–"}</b>
              <span className="muted">{data.youtube.connected ? t("pub.resets", { when: relTime(data.quota.resets_at) }) : t("pub.not_connected_short")}</span>
            </div>
            <div>
              <span className="muted">{t("pub.daily_limit")}</span>
              <b className="mono">{num(data.effective_limit)}</b>
              <span className="muted">{data.best_times.times.join(" · ")}</span>
            </div>
            <a className="btn btn-sm btn-ghost icon-btn" href={href.settings} aria-label={t("pub.settings")} title={t("pub.settings")}>
              <Icon name="settings" />
            </a>
          </div>
        )}
      </div>

      {data && !data.youtube.connected && (
        <div className="notice notice-warn">
          <Icon name="alert" />
          <span>
            {t("pub.plan_without_youtube")} <a href={href.settings}>{t("nav.settings")}</a>
          </span>
        </div>
      )}
      {data?.youtube.connected && !data.youtube.manage && (
        <div className="notice notice-warn">
          <Icon name="alert" />
          <span>
            {t("pub.need_manage")} <a href={href.settings}>{t("nav.settings")}</a>
          </span>
        </div>
      )}
      {data?.youtube.connected && <LockBanner lock={data.youtube.lock} />}
      {data && !data.auto && (
        <div className="notice">
          <Icon name="pause" />
          <span>
            {t("pub.auto_off")} <a href={href.settings}>{t("pub.settings")}</a>
          </span>
        </div>
      )}

      <div className="lib-toolbar">
        <Segmented<"list" | "calendar">
          value={view}
          options={[
            { value: "list", label: t("pub.view_list") },
            { value: "calendar", label: t("pub.view_calendar") },
          ]}
          onChange={(v) => go(href.publish(v))}
          label={t("pub.view")}
        />
        <span style={{ flex: 1 }} />
        <button
          className="btn btn-sm btn-ghost"
          onClick={() =>
            api
              .libraryTick()
              .then(load)
              .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }))
          }
        >
          <Icon name="refresh" />
          {t("pub.check_now")}
        </button>
      </div>

      {!data && !failed && (
        <div className="skeleton-lines">
          {[80, 60, 90].map((w) => (
            <div key={w} className="skeleton" style={{ width: `${w}%`, height: 56 }} />
          ))}
        </div>
      )}

      {data && view === "calendar" && (
        <Calendar rows={rows} limit={data.effective_limit} onOpen={setSetup} onChanged={load} />
      )}

      {data && view === "list" && (
        <>
          <div className="side-tabs lib-tabs" role="tablist" aria-label={t("pub.filter")}>
            {TABS.map((x) => (
              <button key={x} role="tab" aria-selected={tab === x} onClick={() => setTab(x)}>
                {t(`pub.tab.${x}`)}
                <span className="count mono">{num(x === "all" ? rows.length : data.counts[x] ?? 0)}</span>
              </button>
            ))}
          </div>
          {selectable.length > 0 && (
            <div className={`lib-selbar${sel.size ? " on" : ""}`}>
              <label className="inline-row">
                <input type="checkbox" checked={allOn} onChange={(e) => setSel(e.target.checked ? new Set([...sel, ...selectable.map((r) => r.key)]) : new Set())} />
                <span>{sel.size ? t("pub.selected", { n: sel.size }) : t("pub.select_all")}</span>
              </label>
              {sel.size > 0 && (
                <>
                  <button className="btn btn-sm btn-primary" onClick={() => setPlan(selRows)}>
                    <Icon name="calendar" />
                    {t("pub.schedule_selected")}
                  </button>
                  <button className="btn btn-sm btn-ghost" onClick={() => setSel(new Set())}>
                    {t("pub.clear")}
                  </button>
                </>
              )}
            </div>
          )}
          {shown.length === 0 ? (
            <div className="empty">
              <Icon name="film" size={28} />
              <p className="display" style={{ fontSize: 26 }}>
                {t(tab === "all" ? "pub.empty_all" : "pub.empty_tab")}
              </p>
              {tab === "all" && <p className="muted">{t("pub.empty_hint")}</p>}
            </div>
          ) : (
            <ul className="lib-list">
              {shown.map((r) => (
                <Row
                  key={r.key}
                  row={r}
                  selected={sel.has(r.key)}
                  onSelect={(v) => toggle(r.key, v)}
                  onEdit={() => setSetup(r)}
                  onSchedule={() => setPlan([r])}
                  onReschedule={() => setResched(r)}
                  onChanged={load}
                />
              ))}
            </ul>
          )}
        </>
      )}

      {setup && <PublishSetupDialog projectId={setup.project_id} clipId={setup.clip_id} onClose={() => setSetup(null)} onDone={load} />}
      {plan && data && (
        <ScheduleDialog
          rows={plan}
          settings={data}
          onClose={() => setPlan(null)}
          onDone={() => {
            setSel(new Set());
            load();
          }}
        />
      )}
      {resched && <RescheduleDialog row={resched} onClose={() => setResched(null)} onDone={load} />}
    </main>
  );
}

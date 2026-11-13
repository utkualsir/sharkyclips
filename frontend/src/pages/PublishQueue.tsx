// 1.2.40 "Publish queue": approved clips -> files under 10 MB + texts + a calendar for Claude in Chrome
// (no platform APIs). Edit title / description / tags / hashtags / times per clip (the AI's
// suggestions come filled in), "Prepare for Chrome", copy the brief, import the status it answers.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { copyText } from "../extras";
import { fmtTime } from "../format";
import { useI18n } from "../i18n";
import { pqApi, QNAME, QPLATFORMS, toInput, wall, type QClip, type QEntry, type QOverview, type QPlatform, type QResult, type QSlot } from "../pubqueue";
import { useToast } from "../toast";
import { Icon } from "../components/Icons";
import { Modal, ProgressBar, Toggle } from "../components/ui";

const key = (c: { project_id: string; clip_id: string }) => `${c.project_id}/${c.clip_id}`;

/** "Europe/Berlin", or "this computer's time" for the local zone. */
function useZone(ov: QOverview | null) {
  const { t } = useI18n();
  const z = ov?.timezone ?? "local";
  return z === "local" ? t("pq.tz_local") : z;
}

function StatusChip({ p, s }: { p: QPlatform; s: QSlot | undefined }) {
  const { t } = useI18n();
  if (!s) return null;
  const st = s.overdue ? "overdue" : s.status;
  const text = `${QNAME[p]} · ${t(`pq.st_${st}`)}${s.scheduled_at ? ` · ${wall(s.scheduled_at)}` : ""}`;
  const icon =
    st === "scheduled" || st === "published" ? "check" : st === "failed" || st === "overdue" ? "alert" : st === "skipped_duplicate" ? "repeat" : "clock";
  const inner = (
    <>
      <Icon name={icon} size={12} />
      {text}
    </>
  );
  return s.url ? (
    <a className={`pq-chip pq-${st}`} href={s.url} target="_blank" rel="noreferrer" title={s.note ?? undefined}>
      {inner}
    </a>
  ) : (
    <span className={`pq-chip pq-${st}`} title={s.note ?? undefined}>
      {inner}
    </span>
  );
}

function ClipEditor({ clip, ov, auto, onSaved }: { clip: QClip; ov: QOverview; auto: Partial<Record<QPlatform, QSlot>> | undefined; onSaved: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const zone = useZone(ov);
  const d = clip.draft;
  const [title, setTitle] = useState(d.title);
  const [desc, setDesc] = useState(d.description);
  const [tags, setTags] = useState(d.tags.join(", "));
  const [tagsH, setTagsH] = useState(d.hashtags.join(" "));
  useEffect(() => {
    setTitle(d.title);
    setDesc(d.description);
    setTags(d.tags.join(", "));
    setTagsH(d.hashtags.join(" "));
  }, [d]);
  const on = d.platforms ?? QPLATFORMS.filter((p) => ov.settings.platforms[p].on);
  const save = async (body: Parameters<typeof pqApi.draft>[2]) => {
    try {
      await pqApi.draft(clip.project_id, clip.clip_id, body);
      onSaved();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <div className="pq-editor">
      <label className="field">
        <span className="field-label">
          {t("pq.title_f")} <span className={`mp-count${title.length > 100 ? " over" : ""}`}>{title.length}/100</span>
        </span>
        <input className="input" dir="auto" value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => title !== d.title && save({ title })} />
      </label>
      <label className="field">
        <span className="field-label">{t("pq.description")}</span>
        <textarea className="input" dir="auto" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)}
          onBlur={() => desc !== d.description && save({ description: desc })} />
      </label>
      <div className="pq-two">
        <label className="field">
          <span className="field-label">{t("pq.tags")}</span>
          <input className="input" dir="auto" value={tags} onChange={(e) => setTags(e.target.value)}
            onBlur={() => tags !== d.tags.join(", ") && save({ tags: tags.split(",").map((x) => x.trim()).filter(Boolean) })} />
        </label>
        <label className="field">
          <span className="field-label">{t("pq.hashtags")}</span>
          <input className="input" dir="auto" value={tagsH} onChange={(e) => setTagsH(e.target.value)}
            onBlur={() => tagsH !== d.hashtags.join(" ") && save({ hashtags: tagsH.split(/[\s,]+/).filter(Boolean) })} />
          {ov.settings.brand_hashtag && <span className="field-hint">{t("pq.brand_always", { tag: ov.settings.brand_hashtag })}</span>}
        </label>
      </div>
      <div className="pq-plats">
        {QPLATFORMS.map((p) => {
          const enabled = on.includes(p);
          return (
            <div key={p} className={`pq-plat${enabled ? "" : " off"}`}>
              <label className="mp-check">
                <input type="checkbox" checked={enabled}
                  onChange={(e) => save({ platforms: e.target.checked ? [...on, p] : on.filter((x) => x !== p) })} />
                <span>
                  <b>{QNAME[p]}</b>
                  {p === "instagram" && (
                    <span className="muted"> {clip.instagram_account ? `@${clip.instagram_account}` : t("pq.ig_signed_in")}</span>
                  )}
                </span>
              </label>
              {enabled && (
                <label className="field pq-time">
                  <span className="field-hint">{t("pq.time_zone", { tz: zone })}</span>
                  <input
                    className="input"
                    type="datetime-local"
                    value={toInput(d.times[p])}
                    placeholder={wall(auto?.[p]?.scheduled_at)}
                    onChange={(e) => save({ times: { ...d.times, [p]: e.target.value || undefined } })}
                    aria-label={`${QNAME[p]} ${t("pq.time_zone", { tz: zone })}`}
                  />
                  <span className="field-hint">
                    {d.times[p] ? (
                      <button type="button" className="link-btn" onClick={() => save({ times: { ...d.times, [p]: undefined } })}>
                        {t("pq.time_auto")}
                      </button>
                    ) : auto?.[p]?.scheduled_at ? (
                      t("pq.time_auto_is", { when: wall(auto[p]!.scheduled_at, true) })
                    ) : auto?.[p]?.status === "skipped_duplicate" ? (
                      t("pq.st_skipped_duplicate")
                    ) : null}
                  </span>
                </label>
              )}
              {enabled && p === "instagram" && ov.settings.instagram_accounts.length > 1 && (
                <select className="select" value={d.instagram_account ?? ""} onChange={(e) => save({ instagram_account: e.target.value || null })}
                  aria-label={t("pq.ig_account")}>
                  <option value="">{t("pq.ig_auto_short", { name: clip.instagram_account || "?" })}</option>
                  {ov.settings.instagram_accounts.map((a) => (
                    <option key={a} value={a}>
                      @{a}
                    </option>
                  ))}
                </select>
              )}
            </div>
          );
        })}
      </div>
      {d.edited && (
        <button type="button" className="link-btn field-hint" onClick={() => save({ reset: true })}>
          <Icon name="refresh" size={12} /> {t("pq.reset_ai")}
        </button>
      )}
    </div>
  );
}

function SettingsCard({ ov, onChange }: { ov: QOverview; onChange: (o: QOverview) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const zone = useZone(ov);
  const s = ov.settings;
  const [accounts, setAccounts] = useState(s.instagram_accounts.join(", "));
  const [tz, setTz] = useState(s.timezone);
  const [times, setTimes] = useState<Record<QPlatform, string>>(() => ({
    youtube: s.platforms.youtube.times.join(", "),
    tiktok: s.platforms.tiktok.times.join(", "),
    instagram: s.platforms.instagram.times.join(", "),
  }));
  const put = async (body: Parameters<typeof pqApi.settings>[0]) => {
    try {
      onChange(await pqApi.settings(body));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <details className="card pq-settings">
      <summary>
        <Icon name="settings" size={16} /> {t("pq.settings")}
      </summary>
      <p className="field-hint">{t("pq.settings_hint", { tz: zone })}</p>
      <div className="pq-set-grid">
        {QPLATFORMS.map((p) => {
          const c = s.platforms[p];
          return (
            <fieldset key={p} className="pq-set">
              <legend>
                <span className="toggle-row">
                  <Toggle checked={c.on} onChange={(v) => put({ platforms: { [p]: { on: v } } })} label={QNAME[p]} />
                  <b>{QNAME[p]}</b>
                </span>
              </legend>
              <label className="field">
                <span className="field-label">{t("pq.per_day")}</span>
                <input className="input" type="number" min={0} max={ov.caps[p]} value={c.per_day}
                  onChange={(e) => put({ platforms: { [p]: { per_day: Number(e.target.value) } } })} />
                <span className="field-hint">{t("pq.cap", { n: ov.caps[p] })}</span>
              </label>
              <label className="field">
                <span className="field-label">{t("pq.times")}</span>
                <input className="input" value={times[p]} placeholder="12:00, 18:00, 21:00"
                  onChange={(e) => setTimes((x) => ({ ...x, [p]: e.target.value }))}
                  onBlur={() => times[p] !== c.times.join(", ") && put({ platforms: { [p]: { times: times[p].split(",").map((x) => x.trim()).filter(Boolean) } } })} />
              </label>
              {p === "tiktok" && (
                <label className="field">
                  <span className="field-label">{t("pq.tiktok_cap")}</span>
                  <input className="input" type="number" min={1} max={50} value={s.tiktok_cap} onChange={(e) => put({ tiktok_cap: Number(e.target.value) })} />
                </label>
              )}
              {p === "instagram" && (
                <>
                  <label className="field">
                    <span className="field-label">{t("pq.ig_accounts")}</span>
                    <input className="input" dir="ltr" value={accounts} placeholder="@mychannel, @mychannel.gaming"
                      onChange={(e) => setAccounts(e.target.value)}
                      onBlur={() => accounts !== s.instagram_accounts.join(", ") && put({ instagram_accounts: accounts.split(/[\s,;]+/).filter(Boolean) })} />
                    <span className="field-hint">{t("pq.ig_accounts_hint")}</span>
                  </label>
                  {s.instagram_accounts.length > 0 && (
                    <label className="field">
                      <span className="field-label">{t("pq.ig_account")}</span>
                      <select className="select" value={s.instagram_account} onChange={(e) => put({ instagram_account: e.target.value })}>
                        <option value="auto">
                          {t("pq.ig_auto", { gaming: s.instagram_gaming || s.instagram_accounts[0], other: s.instagram_default || s.instagram_accounts[0] })}
                        </option>
                        {s.instagram_accounts.map((a) => (
                          <option key={a} value={a}>
                            @{a}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  {s.instagram_accounts.length > 1 && s.instagram_account === "auto" && (
                    <>
                      <label className="field">
                        <span className="field-label">{t("pq.ig_for_gaming")}</span>
                        <select className="select" value={s.instagram_gaming} onChange={(e) => put({ instagram_gaming: e.target.value })}>
                          {s.instagram_accounts.map((a) => (
                            <option key={a} value={a}>
                              @{a}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span className="field-label">{t("pq.ig_for_rest")}</span>
                        <select className="select" value={s.instagram_default} onChange={(e) => put({ instagram_default: e.target.value })}>
                          {s.instagram_accounts.map((a) => (
                            <option key={a} value={a}>
                              @{a}
                            </option>
                          ))}
                        </select>
                      </label>
                    </>
                  )}
                </>
              )}
            </fieldset>
          );
        })}
      </div>
      <div className="pq-two">
        <label className="field pq-brand">
          <span className="field-label">{t("pq.brand")}</span>
          <input className="input" dir="ltr" placeholder="#mychannel" defaultValue={s.brand_hashtag}
            onBlur={(e) => e.target.value !== s.brand_hashtag && put({ brand_hashtag: e.target.value })} />
          <span className="field-hint">{t("pq.brand_hint")}</span>
        </label>
        <label className="field">
          <span className="field-label">{t("pq.timezone")}</span>
          <input className="input" dir="ltr" list="pq-zones" placeholder={t("pq.tz_local")} value={tz}
            onChange={(e) => setTz(e.target.value)} onBlur={() => tz !== s.timezone && put({ timezone: tz.trim() })} />
          <datalist id="pq-zones">
            {ZONES.map((z) => (
              <option key={z} value={z} />
            ))}
          </datalist>
          <span className="field-hint">{t("pq.timezone_hint", { tz: zone })}</span>
        </label>
      </div>
      <p className="field-hint">
        <Icon name="file" size={12} /> {t("pq.folder", { path: ov.root })}
      </p>
    </details>
  );
}

function ImportDialog({ onClose, onDone }: { onClose: () => void; onDone: (o: QOverview) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const r = await pqApi.importStatus(text);
      onDone(r.overview);
      toast({ kind: r.unmatched.length ? "info" : "ok", text: t("pq.imported", { n: num(r.updated), m: num(r.unmatched.length) }) });
      onClose();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  return (
    <Modal
      top
      title={
        <span className="mp-title">
          <Icon name="download" /> {t("pq.import")}
        </span>
      }
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary" disabled={busy || !text.trim()} onClick={go}>
            {busy ? <span className="spinner" /> : <Icon name="check" />} {t("pq.import_go")}
          </button>
        </>
      }
    >
      <p className="field-hint">{t("pq.import_hint")}</p>
      <textarea className="input mono pq-import" rows={12} value={text} onChange={(e) => setText(e.target.value)}
        placeholder='{"results": [{"id": "…", "platform": "youtube", "status": "scheduled", "url": "https://…"}]}' aria-label={t("pq.import")} />
    </Modal>
  );
}

const ZONES = [
  "Europe/Istanbul", "Europe/Budapest", "Europe/Berlin", "Europe/London", "Europe/Moscow", "Asia/Dubai", "Asia/Riyadh",
  "Asia/Shanghai", "America/New_York", "America/Chicago", "America/Los_Angeles", "UTC",
];

type Mark = "pending" | "scheduled" | "published" | "failed";

function CalendarStatus({ e, onChange }: { e: QEntry; onChange: (o: QOverview) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const set = async (status: Mark) => {
    try {
      const r = await pqApi.mark({ id: e.id, platform: e.platform, batch: e.batch ?? null, status });
      onChange(r.overview);
    } catch (err: any) {
      toast({ kind: "err", text: err.message, hint: err.hint });
    }
  };
  return (
    <span className="pq-status-cell">
      <StatusChip p={e.platform} s={{ ...e, scheduled_at: null }} />
      {e.status !== "skipped_duplicate" && (
        <select className="select select-sm pq-mark" value="" aria-label={t("pq.mark", { title: e.title ?? "" })}
          onChange={(ev) => ev.target.value && set(ev.target.value as Mark)}>
          <option value="">{t("pq.mark_short")}</option>
          {(["published", "scheduled", "pending", "failed"] as const).map((st) => (
            <option key={st} value={st} disabled={st === e.status && !e.overdue}>
              {t(`pq.st_${st}`)}
            </option>
          ))}
        </select>
      )}
    </span>
  );
}

function OverdueBar({ ov, onChange }: { ov: QOverview; onChange: (o: QOverview) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const n = ov.overdue ?? 0;
  if (!n) return null;
  const check = async () => {
    try {
      const r = await pqApi.verify();
      if (await copyText(r.text)) toast({ kind: "ok", text: t("pq.verify_copied", { n: num(r.count) }) });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const replan = async () => {
    try {
      const r = await pqApi.replan();
      onChange(r.overview);
      toast({ kind: "ok", text: t("pq.replanned", { n: num(r.replanned) }) });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <div className="card pq-overdue" role="status">
      <p>
        <Icon name="alert" size={16} /> <b>{t("pq.overdue_title", { n: num(n) })}</b> <span className="muted">{t("pq.overdue_hint")}</span>
      </p>
      <div className="inline-row" style={{ flexWrap: "wrap" }}>
        <button className="btn btn-sm btn-primary" onClick={check}>
          <Icon name="copy" /> {t("pq.verify")}
        </button>
        <button className="btn btn-sm" onClick={replan}>
          <Icon name="calendar" /> {t("pq.replan_all")}
        </button>
      </div>
    </div>
  );
}

export default function PublishQueue() {
  const { t, num } = useI18n();
  const toast = useToast();
  const [ov, setOv] = useState<QOverview | null>(null);
  const zone = useZone(ov);
  const [err, setErr] = useState<string | null>(null);
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [auto, setAuto] = useState<Record<string, Partial<Record<QPlatform, QSlot>>>>({});
  const [autoErr, setAutoErr] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const lastJob = useRef<string | null>(null);

  const load = useCallback(() => {
    pqApi
      .overview()
      .then((o) => {
        setOv(o);
        setErr(null);
      })
      .catch((e) => setErr(e.message));
  }, []);
  useEffect(load, [load]);

  // first load: clips that were never queued are picked
  useEffect(() => {
    if (ov && picked === null) setPicked(new Set(ov.clips.filter((c) => !Object.keys(c.status).length).map(key)));
  }, [ov, picked]);

  const job = ov?.job ?? null;
  const running = !!job && (job.status === "queued" || job.status === "running");
  useEffect(() => {
    if (!running) return;
    const id = window.setTimeout(load, 1500);
    return () => window.clearTimeout(id);
  }, [running, ov, load]);
  useEffect(() => {
    if (job && job.status === "done" && lastJob.current === job.id) {
      toast({ kind: "ok", text: t("pq.ready_toast", { n: num(job.result?.clips.length ?? 0) }) });
      lastJob.current = null;
      setPicked(new Set());
    } else if (job && job.status === "error" && lastJob.current === job.id) {
      toast({ kind: "err", text: job.error?.message ?? t("pq.failed"), hint: job.error?.hint ?? undefined });
      lastJob.current = null;
    }
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const items = useMemo(
    () => (ov && picked ? ov.clips.filter((c) => picked.has(key(c))).map((c) => ({ project_id: c.project_id, clip_id: c.clip_id })) : []),
    [ov, picked],
  );
  // the times the scheduler would give right now (nothing is saved)
  const itemsKey = JSON.stringify(items) + JSON.stringify(ov?.settings) + JSON.stringify(ov?.clips.map((c) => c.draft));
  useEffect(() => {
    if (!items.length) {
      setAuto({});
      setAutoErr(null);
      return;
    }
    const id = window.setTimeout(() => {
      pqApi
        .preview(items)
        .then((r) => {
          setAutoErr(r.ok ? null : r.error?.message ?? null);
          setAuto(Object.fromEntries(r.clips.map((c) => [c.id, c.platforms])));
        })
        .catch(() => {});
    }, 300);
    return () => window.clearTimeout(id);
  }, [itemsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const prepare = async () => {
    try {
      const r = await pqApi.prepare(items);
      lastJob.current = r.job.id;
      load();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const copyBrief = async () => {
    try {
      const b = await pqApi.brief();
      if (await copyText(b.text)) toast({ kind: "ok", text: t("pq.brief_copied", { batch: b.batch }) });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const openFolder = (batch?: string) => pqApi.open(batch).catch(() => {});

  if (!ov) {
    return (
      <main className="page pq-page">
        {err ? <p className="mp-problem">{err}</p> : <div className="card skeleton" style={{ height: 240 }} />}
      </main>
    );
  }
  const result = job?.status === "done" ? ((job.result ?? null) as QResult | null) : null;
  const toggle = (c: QClip) =>
    setPicked((s) => {
      const n = new Set(s ?? []);
      if (n.has(key(c))) n.delete(key(c));
      else n.add(key(c));
      return n;
    });

  return (
    <main className="page pq-page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("pq.title")}</h1>
          <p className="lede">{t("pq.lede")}</p>
        </div>
      </div>

      <section className="card pq-actions" aria-label={t("pq.actions")}>
        <button className="btn btn-primary" disabled={!items.length || running} onClick={prepare}>
          {running ? <span className="spinner" /> : <Icon name="zap" />} {t("pq.prepare", { n: num(items.length) })}
        </button>
        <button className="btn" onClick={copyBrief} disabled={!ov.batches.length}>
          <Icon name="copy" /> {t("pq.copy_brief")}
        </button>
        <button className="btn" onClick={() => setImporting(true)}>
          <Icon name="download" /> {t("pq.import")}
        </button>
        <button className="btn btn-ghost" onClick={() => openFolder(ov.batches[0]?.batch)}>
          <Icon name="file" /> {t("pq.open_folder")}
        </button>
        {running && job && (
          <div className="pq-progress">
            <ProgressBar value={job.progress} label={t(job.stage ? `stage.${job.stage}` : "kind.pubqueue")} />
            <span className="field-hint">
              {t(job.stage ? `stage.${job.stage}` : "kind.pubqueue")}
              {job.progress != null && ` · ${num(Math.round(job.progress * 100))}%`}
            </span>
          </div>
        )}
        {autoErr && (
          <p className="mp-problem" role="alert">
            <Icon name="alert" size={14} /> {autoErr}
          </p>
        )}
      </section>

      {result && (
        <section className="card pq-result" aria-label={t("pq.result")}>
          <header>
            <Icon name="check" size={18} /> <b>{t("pq.result_title", { batch: result.batch })}</b>
          </header>
          <ul className="pq-result-list">
            {result.clips.map((c) => (
              <li key={c.id}>
                <span className="mono">{c.size_mb.toFixed(1)} MB</span> <span dir="auto">{c.title}</span>{" "}
                <span className="muted">{fmtTime(c.duration_s)}</span>
              </li>
            ))}
          </ul>
          {result.errors.map((e) => (
            <p key={e.id} className="mp-fail-line" role="alert">
              <Icon name="alert" size={13} /> {e.title}: {e.message} {e.hint && <span className="muted">{e.hint}</span>}
            </p>
          ))}
          <p className="field-hint">{t("pq.next_step")}</p>
          <div className="inline-row" style={{ flexWrap: "wrap" }}>
            <button className="btn btn-primary btn-sm" onClick={copyBrief}>
              <Icon name="copy" /> {t("pq.copy_brief")}
            </button>
            <button className="btn btn-sm" onClick={() => openFolder(result.batch)}>
              <Icon name="file" /> {t("pq.open_folder")}
            </button>
          </div>
        </section>
      )}

      <section className="pq-section" aria-labelledby="pq-clips">
        <div className="pq-section-head">
          <h2 id="pq-clips">{t("pq.clips")}</h2>
          {ov.clips.length > 0 && (
            <span className="inline-row">
              <button type="button" className="link-btn" onClick={() => setPicked(new Set(ov.clips.map(key)))}>
                {t("pq.pick_all")}
              </button>
              <button type="button" className="link-btn" onClick={() => setPicked(new Set())}>
                {t("pq.pick_none")}
              </button>
            </span>
          )}
        </div>
        {ov.clips.length === 0 ? (
          <p className="card pq-empty">{t("pq.empty")}</p>
        ) : (
          <ul className="pq-list">
            {ov.clips.map((c) => {
              const k = key(c);
              const sel = !!picked?.has(k);
              const plan = auto[c.uid];
              return (
                <li key={k} className={`card pq-row${sel ? " picked" : ""}`}>
                  <div className="pq-row-head">
                    <label className="pq-pick">
                      <input type="checkbox" checked={sel} onChange={() => toggle(c)} aria-label={c.draft.title} />
                    </label>
                    <div className="pq-row-main">
                      <b className="pq-row-title" dir="auto">
                        {c.draft.title}
                      </b>
                      <span className="pq-row-sub" dir="auto">
                        #{String(c.rank ?? "?").padStart(2, "0")} · {fmtTime(c.duration)} · {c.project_title}
                        {!c.rendered && <span className="muted"> · {t("pq.not_rendered")}</span>}
                      </span>
                      <span className="pq-chips">
                        {QPLATFORMS.map((p) => (
                          <StatusChip key={p} p={p} s={c.status[p]} />
                        ))}
                        {sel &&
                          plan &&
                          QPLATFORMS.filter((p) => plan[p] && !c.status[p]).map((p) => (
                            <span key={p} className="pq-chip pq-plan">
                              <Icon name="calendar" size={12} /> {QNAME[p]} · {wall(plan[p]!.scheduled_at)}
                            </span>
                          ))}
                      </span>
                    </div>
                    <button type="button" className="btn btn-sm btn-ghost" aria-expanded={open === k} onClick={() => setOpen(open === k ? null : k)}>
                      <Icon name="wand" size={14} /> {t("pq.edit")}
                    </button>
                  </div>
                  {open === k && <ClipEditor clip={c} ov={ov} auto={plan} onSaved={load} />}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="pq-section" aria-labelledby="pq-cal">
        <div className="pq-section-head">
          <h2 id="pq-cal">{t("pq.calendar")}</h2>
          <span className="field-hint">{t("pq.calendar_hint", { tz: zone })}</span>
        </div>
        <OverdueBar ov={ov} onChange={setOv} />
        {ov.calendar.length === 0 ? (
          <p className="card pq-empty">{t("pq.calendar_empty")}</p>
        ) : (
          <div className="card table-wrap">
            <table className="pq-table">
              <thead>
                <tr>
                  <th>{t("pq.col_date")}</th>
                  <th>{t("pq.col_time")}</th>
                  <th>{t("pq.col_platform")}</th>
                  <th>{t("pq.col_title")}</th>
                  <th>{t("pq.col_status")}</th>
                </tr>
              </thead>
              <tbody>
                {ov.calendar.map((e, i) => (
                  <tr key={`${e.id}-${e.platform}-${i}`}>
                    <td className="mono">{e.scheduled_at ? wall(e.scheduled_at, true).split(" ")[0] : "?"}</td>
                    <td className="mono">{e.scheduled_at ? wall(e.scheduled_at).split(" ")[1] : "?"}</td>
                    <td>
                      {QNAME[e.platform]}
                      {e.platform === "instagram" && e.account && <span className="muted"> @{e.account}</span>}
                    </td>
                    <td dir="auto">{e.title}</td>
                    <td>
                      <CalendarStatus e={e} onChange={setOv} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <SettingsCard ov={ov} onChange={setOv} />
      {importing && <ImportDialog onClose={() => setImporting(false)} onDone={setOv} />}
    </main>
  );
}

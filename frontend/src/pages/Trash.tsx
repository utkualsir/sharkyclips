// 1.2.41 "Çöp kutusu": deleted clips and projects for 30 days (restore / delete for good / empty),
// plus disk usage per project and the "Temizlik" helper (rejected clips, old previews, caches).
import { useCallback, useEffect, useState } from "react";
import { fmtBytes } from "../format";
import { useI18n } from "../i18n";
import { href } from "../router";
import { useToast } from "../toast";
import { trashApi, type DiskUsage, type ProjectUsage, type TrashItem, type TrashSummary } from "../trash";
import { Icon } from "../components/Icons";
import { Modal } from "../components/ui";

type Clean = "rejected" | "previews" | "caches";

function ItemRow({ it, onChange }: { it: TrashItem; onChange: (s: TrashSummary) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [sure, setSure] = useState(false);
  const what =
    it.kind === "project"
      ? t("trash.kind_project")
      : it.kind === "clips"
        ? t("trash.kind_clips", { n: num(it.clip_ids.length) })
        : t("trash.kind_cleanup");
  const restore = async () => {
    setBusy(true);
    try {
      const r = await trashApi.restore(it.id);
      onChange(r.trash);
      toast({ kind: "ok", text: t("trash.restored") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const purge = async () => {
    setBusy(true);
    try {
      const r = await trashApi.purge(it.id);
      onChange(r.trash);
      toast({ kind: "ok", text: t("trash.purged", { size: fmtBytes(r.bytes) }) });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
      setBusy(false);
    }
  };
  const names = it.kind === "cleanup" ? it.titles.map((x) => t(`trash.clean_${x}`)) : it.titles;
  return (
    <li className="card trash-row">
      <div className="trash-main">
        <b dir="auto">{it.kind === "project" ? it.project_title : names.slice(0, 3).join(" · ") || what}</b>
        <span className="field-hint" dir="auto">
          {what}
          {it.kind !== "project" && <> · {it.project_title}</>} · <span className="mono">{fmtBytes(it.bytes)}</span> ·{" "}
          {t("trash.days_left", { n: num(it.days_left) })}
          {it.original?.moved && <> · {t("trash.has_original")}</>}
        </span>
      </div>
      <div className="trash-actions">
        <button className="btn btn-sm" disabled={busy} onClick={restore}>
          <Icon name="refresh" size={14} /> {t("trash.restore")}
        </button>
        {sure ? (
          <>
            <button className="btn btn-sm btn-danger" disabled={busy} onClick={purge}>
              {t("trash.purge_sure")}
            </button>
            <button className="btn btn-sm btn-ghost" onClick={() => setSure(false)}>
              {t("common.cancel")}
            </button>
          </>
        ) : (
          <button className="btn btn-sm btn-ghost btn-danger-text" disabled={busy} onClick={() => setSure(true)}>
            <Icon name="trash" size={14} /> {t("trash.purge")}
          </button>
        )}
      </div>
    </li>
  );
}

function EmptyDialog({ s, onClose, onDone }: { s: TrashSummary; onClose: () => void; onDone: (s: TrashSummary) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const r = await trashApi.empty(s.count);
      onDone(r.trash);
      toast({ kind: r.left ? "info" : "ok", text: t("trash.emptied", { n: num(r.deleted), size: fmtBytes(r.bytes) }) });
      onClose();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
      setBusy(false);
    }
  };
  return (
    <Modal
      top
      title={
        <span className="mp-title">
          <Icon name="alert" /> {t("trash.empty_title")}
        </span>
      }
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-danger" disabled={busy} onClick={go} data-testid="trash-empty-confirm">
            {busy ? <span className="spinner" /> : <Icon name="trash" />} {t("trash.empty_go", { n: num(s.count), size: fmtBytes(s.bytes) })}
          </button>
        </>
      }
    >
      <p>
        <b>{t("trash.empty_body", { n: num(s.count), size: fmtBytes(s.bytes) })}</b>
      </p>
      <p className="field-hint">{t("trash.empty_hint")}</p>
    </Modal>
  );
}

function UsageRow({ u, onCleaned }: { u: ProjectUsage; onCleaned: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [pick, setPick] = useState<Set<Clean>>(() => new Set((["rejected", "previews", "caches"] as Clean[]).filter((k) => u.cleanable[k].bytes > 0)));
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const r = await trashApi.cleanup(u.project_id, [...pick]);
      toast({ kind: "ok", text: t("trash.cleaned", { size: fmtBytes(r.freed_now + (r.trashed?.bytes ?? 0)) }), hint: r.trashed ? t("trash.cleaned_hint") : undefined });
      onCleaned();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const parts: [string, number][] = [
    [t("trash.part_source"), u.source + u.audio],
    [t("trash.part_clips"), u.clips + u.exports],
    [t("trash.part_cache"), u.cache + u.other],
  ];
  const opts: [Clean, number, string][] = [
    ["rejected", u.cleanable.rejected.bytes, t("trash.clean_rejected_n", { n: num(u.cleanable.rejected.clips) })],
    ["previews", u.cleanable.previews.bytes, t("trash.clean_previews")],
    ["caches", u.cleanable.caches.bytes, t("trash.clean_caches")],
  ];
  const sel = opts.filter(([k]) => pick.has(k)).reduce((a, [, b]) => a + b, 0);
  return (
    <li className="card trash-usage">
      <div className="trash-main">
        <a href={href.project(u.project_id)} dir="auto">
          <b>{u.title}</b>
        </a>
        <span className="field-hint">
          <span className="mono">{fmtBytes(u.total)}</span> · {parts.map(([k, v]) => `${k} ${fmtBytes(v)}`).join(" · ")}
        </span>
      </div>
      {u.cleanable_bytes > 0 ? (
        <div className="trash-clean">
          {opts
            .filter(([, b]) => b > 0)
            .map(([k, b, label]) => (
              <label key={k} className="mp-check">
                <input
                  type="checkbox"
                  checked={pick.has(k)}
                  onChange={(e) =>
                    setPick((s) => {
                      const n = new Set(s);
                      if (e.target.checked) n.add(k);
                      else n.delete(k);
                      return n;
                    })
                  }
                />
                <span>
                  {label} <span className="mono">{fmtBytes(b)}</span>
                </span>
              </label>
            ))}
          <button className="btn btn-sm" disabled={busy || !pick.size} onClick={go}>
            <Icon name="zap" size={14} /> {t("trash.clean_go", { size: fmtBytes(sel) })}
          </button>
        </div>
      ) : (
        <span className="field-hint">{t("trash.clean_nothing")}</span>
      )}
    </li>
  );
}

export default function Trash() {
  const { t, num } = useI18n();
  const [s, setS] = useState<TrashSummary | null>(null);
  const [disk, setDisk] = useState<DiskUsage | null>(null);
  const [emptying, setEmptying] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const loadDisk = useCallback(() => {
    trashApi.disk().then(setDisk).catch(() => {});
  }, []);
  const load = useCallback(() => {
    trashApi
      .list()
      .then(setS)
      .catch((e) => setErr(e.message));
    loadDisk();
  }, [loadDisk]);
  useEffect(load, [load]);
  const change = (n: TrashSummary) => {
    setS(n);
    loadDisk();
  };
  return (
    <main className="page trash-page">
      <div className="page-head">
        <div>
          <h1 className="display">{t("trash.title")}</h1>
          <p className="lede">{t("trash.lede", { days: num(s?.keep_days ?? 30) })}</p>
        </div>
        {s && s.count > 0 && (
          <button className="btn btn-danger" onClick={() => setEmptying(true)}>
            <Icon name="trash" /> {t("trash.empty")}
          </button>
        )}
      </div>
      {err && <p className="mp-problem">{err}</p>}
      <section className="trash-section" aria-labelledby="trash-items">
        <div className="pq-section-head">
          <h2 id="trash-items">{t("trash.items")}</h2>
          {s && s.count > 0 && (
            <span className="field-hint">
              {t("trash.total", { n: num(s.count), size: fmtBytes(s.bytes) })}
            </span>
          )}
        </div>
        {!s ? (
          <div className="card skeleton" style={{ height: 120 }} />
        ) : s.items.length === 0 ? (
          <p className="card pq-empty">{t("trash.nothing")}</p>
        ) : (
          <ul className="trash-list">
            {s.items.map((it) => (
              <ItemRow key={it.id} it={it} onChange={change} />
            ))}
          </ul>
        )}
      </section>
      <section className="trash-section" aria-labelledby="trash-disk">
        <div className="pq-section-head">
          <h2 id="trash-disk">{t("trash.disk")}</h2>
          {disk && (
            <span className="field-hint">
              {t("trash.disk_total", { size: fmtBytes(disk.total), clean: fmtBytes(disk.cleanable_bytes) })}
            </span>
          )}
        </div>
        <p className="field-hint">{t("trash.disk_hint")}</p>
        {!disk ? (
          <div className="card skeleton" style={{ height: 120 }} />
        ) : disk.projects.length === 0 ? (
          <p className="card pq-empty">{t("trash.no_projects")}</p>
        ) : (
          <ul className="trash-list">
            {disk.projects.map((u) => (
              <UsageRow key={u.project_id} u={u} onCleaned={load} />
            ))}
          </ul>
        )}
      </section>
      {emptying && s && <EmptyDialog s={s} onClose={() => setEmptying(false)} onDone={change} />}
    </main>
  );
}

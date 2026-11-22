// 1.2.41: delete clips / projects into the trash, with an undo toast.
// 1.2.47: planned posts that aren't on the platform yet (keep / cancel), the keep-days setting
// (0 = deleted for good at once) and the trash card in Settings.
import { useEffect, useState } from "react";
import { fmtBytes } from "../format";
import { useI18n } from "../i18n";
import { href } from "../router";
import { useToast } from "../toast";
import { trashApi, type DeleteInfo, type TrashItem, type TrashSummary } from "../trash";
import { Icon } from "./Icons";
import { Modal, Sep } from "./ui";

const PLATFORM: Record<string, string> = { youtube: "YouTube", tiktok: "TikTok", reels: "Instagram" };

/** The toast after a delete: "Moved to the trash" + Undo (or "deleted for good" with 0 keep days). */
export function useUndoToast() {
  const { t, num } = useI18n();
  const toast = useToast();
  return (item: TrashItem, onRestored: () => void) => {
    const n = item.kind === "project" ? 1 : item.clip_ids.length;
    const kept = item.kept_posts?.length ?? 0;
    if (item.purged) {
      toast({
        kind: "ok",
        text: t("trash.purged", { size: fmtBytes(item.bytes) }),
        hint: kept ? t("trash.kept_hint", { n: num(kept) }) : undefined,
      });
      return;
    }
    toast({
      kind: "ok",
      text: item.kind === "project" ? t("trash.moved_project", { title: item.project_title }) : t("trash.moved_clips", { n }),
      hint: kept ? t("trash.kept_hint", { n: num(kept) }) : t("trash.moved_hint", { days: item.days_left }),
      ms: 9000,
      action: {
        label: t("trash.undo"),
        run: () => {
          trashApi
            .restore(item.id)
            .then(() => {
              toast({ kind: "ok", text: t("trash.restored") });
              onRestored();
            })
            .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
        },
      },
    });
  };
}

/** Confirm a delete: what goes, how big, the original video, planned posts and the posts out there. */
export function DeleteDialog({
  projectId,
  clipIds,
  onClose,
  onDeleted,
}: {
  projectId: string;
  /** null = the whole project */
  clipIds: string[] | null;
  onClose: () => void;
  onDeleted: (item: TrashItem) => void;
}) {
  const { t, num, lang } = useI18n();
  const toast = useToast();
  const [info, setInfo] = useState<DeleteInfo | null>(null);
  const [original, setOriginal] = useState(false);
  const [posts, setPosts] = useState(false);
  const [pending, setPending] = useState<"keep" | "cancel">("keep");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    trashApi
      .info(projectId, clipIds ?? undefined)
      .then((i) => {
        setInfo(i);
        setPending(i.keep_possible ? "keep" : "cancel");
      })
      .catch((e) => {
        toast({ kind: "err", text: e.message, hint: e.hint });
        onClose();
      });
  }, [projectId, clipIds?.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const whole = clipIds === null;
  const go = async () => {
    setBusy(true);
    try {
      if (whole) {
        const r = await trashApi.deleteProject(projectId, { original, posts, pending });
        if (!r.item) {
          // an export comes first (a kept post had no up-to-date video): a job does the rest
          toast({ kind: "info", text: t("trash.keep_job"), hint: t("trash.keep_job_hint") });
          onClose();
          return;
        }
        report(r.item);
      } else {
        report((await trashApi.deleteClips(projectId, clipIds!, posts)).item);
      }
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
      setBusy(false);
    }
  };
  const report = (item: TrashItem) => {
    const byHand = item.posts?.by_hand ?? [];
    const failed = item.posts?.failed ?? [];
    if (byHand.length || failed.length)
      toast({
        kind: "info",
        text: t("trash.posts_by_hand", { n: num(byHand.length + failed.length) }),
        hint: [...byHand, ...failed].map((p) => `${PLATFORM[p.platform] ?? p.platform}: ${p.url ?? p.id ?? "?"}`).join(", "),
      });
    if (item.original?.error) toast({ kind: "err", text: t("trash.original_failed"), hint: item.original.error });
    onDeleted(item);
  };
  const deletable = (info?.posts ?? []).filter((p) => p.platform === "youtube" || p.can_delete);
  const manual = (info?.posts ?? []).filter((p) => !(p.platform === "youtube" || p.can_delete));
  const local = (info?.pending ?? []).filter((p) => !p.on_platform);
  const zero = info?.keep_days === 0;
  const when = (iso: string | null) =>
    iso ? new Date(iso).toLocaleString(lang, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "–";
  return (
    <Modal
      top
      title={
        <span className="mp-title">
          <Icon name="trash" /> {whole ? t("trash.delete_project") : t("trash.delete_clips", { n: num(clipIds!.length) })}
        </span>
      }
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-danger" disabled={busy || !info} onClick={go} data-testid="trash-confirm">
            {busy ? <span className="spinner" /> : <Icon name="trash" />} {zero ? t("trash.purge") : t("trash.move")}
          </button>
        </>
      }
    >
      {!info ? (
        <div className="skeleton" style={{ height: 80 }} />
      ) : (
        <div className="trash-dialog">
          <p>
            {whole ? (
              <b dir="auto">{info.title}</b>
            ) : (
              <b>{t("trash.n_clips", { n: num(clipIds!.length) })}</b>
            )}{" "}
           <Sep /><span className="mono">{fmtBytes(info.bytes)}</span>
          </p>
          <p className={`field-hint${zero ? " trash-zero" : ""}`}>
            {zero ? t("trash.keep_hint_off") : t("trash.keep_hint", { days: num(info.keep_days) })}
          </p>
          {local.length > 0 && (
            <div className="trash-pending" role="alert" data-testid="trash-pending">
              <p>
                <Icon name="alert" size={15} /> <b>{t("trash.pending_title", { n: num(local.length) })}</b>
              </p>
              <p className="field-hint">{t("trash.pending_checked")}</p>
              <ul className="trash-posts">
                {local.map((p, i) => (
                  <li key={i}>
                    <b>{PLATFORM[p.platform] ?? p.platform}</b><Sep /><span className="mono">{when(p.publish_at)}</span><Sep />
                    <span dir="auto">{p.title}</span>
                  </li>
                ))}
              </ul>
              {whole ? (
                <div className="trash-pending-opts" role="radiogroup" aria-label={t("trash.pending_title", { n: num(local.length) })}>
                  <label className={`mp-check trash-opt${info.keep_possible ? "" : " disabled"}`}>
                    <input
                      type="radio"
                      name="trash-pending"
                      checked={pending === "keep"}
                      disabled={!info.keep_possible}
                      onChange={() => setPending("keep")}
                    />
                    <span>
                      <b>{t("trash.pending_keep")}</b>
                      <span className="field-hint">
                        {info.keep_possible ? t("trash.pending_keep_hint") : t("trash.pending_keep_wait")}
                      </span>
                      {info.keep_possible && info.keep_bytes > 0 && (
                        <span className="field-hint">{t("trash.pending_keep_size", { size: fmtBytes(info.keep_bytes) })}</span>
                      )}
                      {info.keep_possible && local.some((p) => p.platform === "reels") && (
                        <span className="field-hint">{t("trash.pending_keep_ig")}</span>
                      )}
                      {info.keep_possible && info.keep_needs_export > 0 && (
                        <span className="field-hint">{t("trash.pending_keep_export", { n: num(info.keep_needs_export) })}</span>
                      )}
                    </span>
                  </label>
                  <label className="mp-check trash-opt">
                    <input type="radio" name="trash-pending" checked={pending === "cancel"} onChange={() => setPending("cancel")} />
                    <span>
                      <b>{t("trash.pending_cancel")}</b>
                      <span className="field-hint">{t("trash.pending_cancel_hint")}</span>
                    </span>
                  </label>
                </div>
              ) : (
                <p className="field-hint">{t("trash.pending_clips")}</p>
              )}
            </div>
          )}
          {info.pending_on_platform > 0 && (
            <p className="field-hint">
              <Icon name="check" size={13} /> {t("trash.pending_on_platform", { n: num(info.pending_on_platform) })}
            </p>
          )}
          {whole && info.original && (
            <label className="mp-check trash-opt">
              <input type="checkbox" checked={original} onChange={(e) => setOriginal(e.target.checked)} />
              <span>
                <b>{t("trash.with_original")}</b> <span className="mono">{fmtBytes(info.original.bytes)}</span>
                <span className="field-hint trash-path" dir="ltr">
                  {info.original.path}
                </span>
                <span className="field-hint">{t(info.original.outside_workspace ? "trash.original_outside" : "trash.original_inside")}</span>
              </span>
            </label>
          )}
          {whole && !info.original && <p className="field-hint">{t("trash.no_original")}</p>}
          {deletable.length > 0 && (
            <label className="mp-check trash-opt danger">
              <input type="checkbox" checked={posts} onChange={(e) => setPosts(e.target.checked)} />
              <span>
                <b>{t("trash.with_posts", { n: num(deletable.length) })}</b>
                <span className="field-hint">{t("trash.with_posts_hint")}</span>
                <ul className="trash-posts">
                  {info.posts.map((p, i) => (
                    <li key={i}>
                      {PLATFORM[p.platform] ?? p.platform}
                      {p.url ? (
                        <>
                          <Sep />
                          <a href={p.url} target="_blank" rel="noreferrer" dir="ltr">
                            {p.url.replace(/^https:\/\/(www\.)?/, "").slice(0, 48)}
                          </a>
                        </>
                      ) : null}
                    </li>
                  ))}
                </ul>
                {manual.length > 0 && <span className="field-hint">{t("trash.posts_manual_note")}</span>}
              </span>
            </label>
          )}
          {!posts && info.posts.length > 0 && <p className="field-hint">{t("trash.posts_stay")}</p>}
        </div>
      )}
    </Modal>
  );
}

/** "Empty trash": everything in it, for good (the server checks the count shown here). */
export function EmptyDialog({ s, onClose, onDone }: { s: TrashSummary; onClose: () => void; onDone: (s: TrashSummary) => void }) {
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

/** Settings: how much the trash takes, "Empty trash", and how many days it keeps things. */
export function TrashCard({ easy = false }: { easy?: boolean }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [s, setS] = useState<TrashSummary | null>(null);
  const [days, setDays] = useState("");
  const [emptying, setEmptying] = useState(false);
  const [saving, setSaving] = useState(false);
  const show = (x: TrashSummary) => {
    setS(x);
    setDays(String(x.keep_days));
  };
  useEffect(() => {
    trashApi.list().then(show).catch(() => {});
  }, []);
  const n = Number(days);
  const valid = days.trim() !== "" && Number.isInteger(n) && n >= 0 && n <= 365;
  const dirty = !!s && valid && n !== s.keep_days;
  const save = async () => {
    setSaving(true);
    try {
      show(await trashApi.setKeepDays(n));
      toast({ kind: "ok", text: t("common.saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setSaving(false);
  };
  const head = (
    <div>
      <h2 id="set-trash">{t("trash.title")}</h2>
      <p className={easy ? "muted" : undefined} style={easy ? { marginTop: 0 } : undefined}>
        {t("trash.settings_desc")}
      </p>
    </div>
  );
  const body = !s ? (
    <div className="skeleton" style={{ height: 90 }} />
  ) : (
    <div className="trash-card">
      <div className="trash-card-use">
        <span className="trash-card-size mono" data-testid="trash-size">
          {fmtBytes(s.bytes)}
        </span>
        <span className="muted">{s.count ? t("trash.count", { n: num(s.count) }) : t("trash.nothing")}</span>
      </div>
      <div className="trash-card-actions">
        <button className="btn btn-danger" disabled={!s.count} onClick={() => setEmptying(true)} data-testid="trash-empty">
          <Icon name="trash" size={15} /> {t("trash.empty")}
        </button>
        <a className="btn btn-ghost" href={href.trash}>
          {t("trash.open")}
        </a>
      </div>
      <div>
        <label className="field-label" htmlFor="trash-days" style={{ display: "block", marginBottom: 6 }}>
          {t("trash.keep_days")}
        </label>
        <div className="trash-card-days">
          <input
            id="trash-days"
            className="input mono"
            type="number"
            inputMode="numeric"
            min={0}
            max={365}
            value={days}
            aria-invalid={!valid}
            onChange={(e) => setDays(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && dirty && save()}
          />
          <span className="muted">{t("trash.days_unit")}</span>
          <button className="btn btn-primary" disabled={!dirty || saving} onClick={save}>
            {saving ? <span className="spinner" /> : null} {t("common.save")}
          </button>
        </div>
        <div className={`field-hint${valid && n === 0 ? " trash-zero" : ""}`} style={{ marginTop: 6 }}>
          {valid && n === 0 ? t("trash.keep_days_off") : t("trash.keep_days_hint")}
        </div>
      </div>
      {emptying && <EmptyDialog s={s} onClose={() => setEmptying(false)} onDone={show} />}
    </div>
  );
  return easy ? (
    <section className="card ez-set-card" id="trash" aria-labelledby="set-trash">
      {head}
      {body}
    </section>
  ) : (
    <section className="card setting" id="trash" aria-labelledby="set-trash">
      {head}
      {body}
    </section>
  );
}

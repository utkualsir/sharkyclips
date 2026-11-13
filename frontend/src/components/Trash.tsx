// 1.2.41: delete clips / projects into the 30-day trash, with an undo toast.
import { useEffect, useState } from "react";
import { fmtBytes } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { trashApi, type DeleteInfo, type TrashItem } from "../trash";
import { Icon } from "./Icons";
import { Modal } from "./ui";

const PLATFORM: Record<string, string> = { youtube: "YouTube", tiktok: "TikTok", reels: "Instagram" };

/** The toast after a delete: "Moved to the trash" + Undo. */
export function useUndoToast() {
  const { t } = useI18n();
  const toast = useToast();
  return (item: TrashItem, onRestored: () => void) => {
    const n = item.kind === "project" ? 1 : item.clip_ids.length;
    toast({
      kind: "ok",
      text: item.kind === "project" ? t("trash.moved_project", { title: item.project_title }) : t("trash.moved_clips", { n }),
      hint: t("trash.moved_hint", { days: item.days_left }),
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

/** Confirm a delete: what goes, how big, the original video and the posts (only when ticked). */
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
  const { t, num } = useI18n();
  const toast = useToast();
  const [info, setInfo] = useState<DeleteInfo | null>(null);
  const [original, setOriginal] = useState(false);
  const [posts, setPosts] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    trashApi
      .info(projectId, clipIds ?? undefined)
      .then(setInfo)
      .catch((e) => {
        toast({ kind: "err", text: e.message, hint: e.hint });
        onClose();
      });
  }, [projectId, clipIds?.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const whole = clipIds === null;
  const go = async () => {
    setBusy(true);
    try {
      const r = whole
        ? await trashApi.deleteProject(projectId, { original, posts })
        : await trashApi.deleteClips(projectId, clipIds!, posts);
      const byHand = r.item.posts?.by_hand ?? [];
      const failed = r.item.posts?.failed ?? [];
      if (byHand.length || failed.length)
        toast({
          kind: "info",
          text: t("trash.posts_by_hand", { n: num(byHand.length + failed.length) }),
          hint: [...byHand, ...failed].map((p) => `${PLATFORM[p.platform] ?? p.platform}: ${p.url ?? p.id ?? "?"}`).join(" · "),
        });
      if (r.item.original?.error) toast({ kind: "err", text: t("trash.original_failed"), hint: r.item.original.error });
      onDeleted(r.item);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
      setBusy(false);
    }
  };
  const deletable = (info?.posts ?? []).filter((p) => p.platform === "youtube" || p.can_delete);
  const manual = (info?.posts ?? []).filter((p) => !(p.platform === "youtube" || p.can_delete));
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
            {busy ? <span className="spinner" /> : <Icon name="trash" />} {t("trash.move")}
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
            · <span className="mono">{fmtBytes(info.bytes)}</span>
          </p>
          <p className="field-hint">{t("trash.keep_hint", { days: num(info.keep_days) })}</p>
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
          {info.posts.length > 0 && (
            <label className={`mp-check trash-opt danger${deletable.length ? "" : " disabled"}`}>
              <input type="checkbox" checked={posts} disabled={!deletable.length} onChange={(e) => setPosts(e.target.checked)} />
              <span>
                <b>{t("trash.with_posts", { n: num(deletable.length) })}</b>
                <span className="field-hint">{t("trash.with_posts_hint")}</span>
                <ul className="trash-posts">
                  {info.posts.map((p, i) => (
                    <li key={i}>
                      {PLATFORM[p.platform] ?? p.platform}
                      {p.url ? (
                        <>
                          {" · "}
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

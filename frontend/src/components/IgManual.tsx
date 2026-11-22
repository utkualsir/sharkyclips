// 1.2.50: Instagram Manual mode. Meta restricted the account for automation, so SharkyClips never
// posts to Instagram by itself any more: at the planned time it reminds you (Windows notice + this
// bar on every screen), the guide copies the title / description / hashtags and opens the folder,
// you post from the Instagram app. Automatic posts planned before 1.2.50 are "paused": listed
// here, sent nowhere, until you prepare them by hand.
import { useCallback, useEffect, useState } from "react";
import { useAppState } from "../appstate";
import { useI18n } from "../i18n";
import { igManualApi, openHandoff, type IgManual, type IgManualRow } from "../multipost";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Modal } from "./ui";

function when(iso: string | null, lang: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(lang, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function IgManualBar() {
  const { t } = useI18n();
  const { state } = useAppState();
  const [open, setOpen] = useState(false);
  const s = state?.instagram_manual ?? null;
  useEffect(() => {
    const on = () => setOpen(true);
    window.addEventListener("sc-ig-manual", on);
    return () => window.removeEventListener("sc-ig-manual", on);
  }, []);
  return (
    <>
      {s && (s.due > 0 || s.paused > 0) && (
        <div className={`igm-bar${s.due > 0 ? " igm-bar-due" : ""}`} role="status">
          <Icon name={s.due > 0 ? "bell" : "pause"} size={15} />
          <span className="igm-bar-text">
            {s.due > 0 && <b>{t("igm.bar_due", { n: s.due })}</b>}
            {s.due > 0 && s.paused > 0 && ", "}
            {s.paused > 0 && <span>{t("igm.bar_paused", { n: s.paused })}</span>}
          </span>
          <button type="button" className="btn btn-sm" onClick={() => setOpen(true)}>
            {t("igm.bar_open")}
          </button>
        </div>
      )}
      {open && <IgManualDialog onClose={() => setOpen(false)} />}
    </>
  );
}

function IgManualDialog({ onClose }: { onClose: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { refresh } = useAppState();
  const [data, setData] = useState<IgManual | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = useCallback(() => {
    igManualApi
      .list()
      .then(setData)
      .catch(() => {});
  }, []);
  useEffect(() => {
    load();
    const on = () => {
      load();
      refresh();
    };
    window.addEventListener("sc-posts-changed", on);
    return () => window.removeEventListener("sc-posts-changed", on);
  }, [load, refresh]);
  useEffect(() => {
    if (!data?.preparing.length) return;
    const id = window.setTimeout(load, 1500);
    return () => window.clearTimeout(id);
  }, [data, load]);

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    try {
      await fn();
      load();
      refresh();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(null);
  };
  const share = (r: IgManualRow) => {
    openHandoff({ pid: r.project_id, cid: r.clip_id, title: r.title, platforms: ["reels"] });
    onClose();
  };
  const key = (r: IgManualRow) => `${r.project_id}/${r.clip_id}`;

  const row = (r: IgManualRow, actions: React.ReactNode) => (
    <li key={key(r)} className="igm-row">
      <span className="igm-row-main">
        <b dir="auto">{r.title}</b>
        <span className="muted" dir="auto">
          {when(r.when, lang)}
          {r.when ? ", " : ""}
          {r.project_title}
        </span>
      </span>
      <span className="igm-row-act">{actions}</span>
    </li>
  );

  return (
    <Modal
      top
      title={
        <span className="mp-title">
          <Icon name="bell" /> {t("igm.title")}
        </span>
      }
      onClose={onClose}
      footer={
        <button type="button" className="btn" onClick={onClose}>
          {t("common.close")}
        </button>
      }
    >
      <p className="field-hint">{t("igm.why")}</p>
      {!data ? (
        <p className="ho-line">
          <span className="spinner" /> {t("common.loading")}
        </p>
      ) : (
        <>
          {data.due.length > 0 && (
            <section className="igm-sec" aria-label={t("igm.sec_due")}>
              <h3>{t("igm.sec_due")}</h3>
              <ul className="igm-list">
                {data.due.map((r) =>
                  row(
                    r,
                    <>
                      <button type="button" className="btn btn-sm btn-primary" onClick={() => share(r)}>
                        <Icon name="copy" size={14} /> {t("igm.share")}
                      </button>
                      <button type="button" className="btn btn-sm btn-ghost" disabled={busy === key(r)}
                        onClick={() => run(key(r), () => igManualApi.snooze(r.project_id, r.clip_id, 60))}>
                        {t("igm.later")}
                      </button>
                    </>,
                  ),
                )}
              </ul>
            </section>
          )}
          {(data.upcoming.length > 0 || data.preparing.length > 0) && (
            <section className="igm-sec" aria-label={t("igm.sec_upcoming")}>
              <h3>{t("igm.sec_upcoming")}</h3>
              <ul className="igm-list">
                {data.preparing.map((r) => row(r, <span className="spinner spinner-xs" aria-label={t("mp.st_preparing")} />))}
                {data.upcoming.map((r) =>
                  row(
                    r,
                    <button type="button" className="btn btn-sm" onClick={() => share(r)}>
                      <Icon name="copy" size={14} /> {t("igm.share_now")}
                    </button>,
                  ),
                )}
              </ul>
            </section>
          )}
          {data.paused.length > 0 && (
            <section className="igm-sec" aria-label={t("igm.sec_paused")}>
              <h3>{t("igm.sec_paused")}</h3>
              <p className="field-hint">{t("igm.paused_note")}</p>
              <ul className="igm-list">
                {data.paused.map((r) =>
                  row(
                    r,
                    <button type="button" className="btn btn-sm" disabled={busy === key(r)}
                      onClick={() => run(key(r), () => igManualApi.prepare(r.project_id, r.clip_id))}>
                      {busy === key(r) ? <span className="spinner spinner-xs" /> : <Icon name="upload" size={14} />} {t("igm.prepare")}
                    </button>,
                  ),
                )}
              </ul>
              {data.paused.length > 1 && (
                <button type="button" className="btn" disabled={busy === "all"} onClick={() => run("all", () => igManualApi.prepareAll())}>
                  {busy === "all" ? <span className="spinner spinner-xs" /> : <Icon name="upload" size={14} />} {t("igm.prepare_all")}
                </button>
              )}
            </section>
          )}
          {!data.due.length && !data.upcoming.length && !data.paused.length && !data.preparing.length && (
            <p className="field-hint">{t("igm.empty")}</p>
          )}
        </>
      )}
    </Modal>
  );
}

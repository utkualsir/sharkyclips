// 1.2.68 "Upload manually": for every platform and every clip. SharkyClips saves the video that
// fits the platform, shows each text with its own copy button, opens the upload page and the
// file's folder. "I posted it" marks the clip shared there (and in the upload history).
import { useCallback, useEffect, useState } from "react";
import { useI18n } from "../i18n";
import { TARGET_NAME, type Target } from "../multipost";
import { manualApi, shareChanged, type ManualView } from "../share";
import { useToast } from "../toast";
import { useMeta } from "../meta";
import { Icon } from "./Icons";
import { PlatformIcon } from "./PlatformIcons";
import { Modal, ProgressBar } from "./ui";

const ORDER: Target[] = ["youtube", "tiktok", "reels"];

function CopyField({ label, value, rows }: { label: string; value: string; rows?: number }) {
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  const copy = () => {
    navigator.clipboard
      ?.writeText(value)
      .then(() => {
        setDone(true);
        window.setTimeout(() => setDone(false), 1600);
      })
      .catch(() => {});
  };
  return (
    <div className="mu-field">
      <div className="mu-field-head">
        <span className="field-label">{label}</span>
        <button type="button" className={`btn btn-sm${done ? " btn-primary" : ""}`} onClick={copy} disabled={!value}>
          <Icon name={done ? "check" : "copy"} /> {done ? t("common.copied") : t("common.copy")}
        </button>
      </div>
      {rows && rows > 1 ? (
        <textarea className="input mu-text" dir="auto" readOnly rows={rows} value={value} aria-label={label} />
      ) : (
        <input className="input mu-text" dir="auto" readOnly value={value} aria-label={label} />
      )}
    </div>
  );
}

export function ManualUpload({
  pid,
  cid,
  title,
  platform,
  platforms,
  onClose,
}: {
  pid: string;
  cid: string;
  title: string;
  platform: Target;
  platforms?: Target[];
  onClose: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const meta = useMeta();
  const [p, setP] = useState<Target>(platform);
  const [v, setV] = useState<ManualView | null>(null);
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const list = (platforms?.length ? platforms : ORDER).filter((x) => ORDER.includes(x));

  const load = useCallback(
    (prepare: boolean) => {
      const call = prepare ? manualApi.prepare(pid, cid, p) : manualApi.view(pid, cid, p);
      return call.then(setV).catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
    },
    [pid, cid, p, toast],
  );
  useEffect(() => {
    setV(null);
    load(true);
  }, [load]);
  useEffect(() => {
    if (v?.status !== "preparing") return;
    const iv = window.setInterval(() => load(false), 1500);
    return () => window.clearInterval(iv);
  }, [v?.status, load]);

  const openFolder = () =>
    manualApi.open(pid, cid, p).catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  const openPage = () => {
    if (v) window.open(v.upload_page, "_blank", "noopener");
    if (meta?.is_local) openFolder();
  };
  const done = () => {
    setBusy(true);
    manualApi
      .done(pid, cid, p, link)
      .then((x) => {
        setV(x);
        shareChanged();
        toast({ kind: "ok", text: t("mu.marked", { name: TARGET_NAME[p] }) });
        onClose();
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }))
      .finally(() => setBusy(false));
  };

  const ready = v?.status === "ready" || v?.status === "shared";
  return (
    <Modal
      title={t("mu.title")}
      onClose={onClose}
      wide
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            {t("common.close")}
          </button>
          <span style={{ flex: 1 }} />
          <button type="button" className="btn btn-primary" onClick={done} disabled={!ready || busy}>
            <Icon name="check" /> {t("mu.posted", { name: TARGET_NAME[p] })}
          </button>
        </>
      }
    >
      <p className="muted mu-clip" dir="auto" style={{ marginTop: 0 }}>
        {title}
      </p>
      {list.length > 1 && (
        <div className="share-tabs mu-tabs" role="group" aria-label={t("mu.platform")}>
          {list.map((x) => (
            <button key={x} type="button" aria-pressed={p === x} onClick={() => setP(x)}>
              <PlatformIcon p={x} size={15} /> {TARGET_NAME[x]}
            </button>
          ))}
        </div>
      )}
      {!v || v.status === "preparing" ? (
        <div className="mu-wait" role="status">
          <span className="spinner" aria-hidden="true" /> {t("mu.preparing")}
          <ProgressBar value={v?.progress ?? null} label={t("mu.preparing")} />
        </div>
      ) : v.status === "failed" ? (
        <div className="notice notice-danger" role="alert">
          <Icon name="alert" />
          <div style={{ flex: 1 }}>
            <div className="notice-title">{v.error?.message ?? t("common.error")}</div>
            {v.error?.hint && <div className="muted">{v.error.hint}</div>}
          </div>
          <button type="button" className="btn" onClick={() => load(true)}>
            <Icon name="refresh" /> {t("common.retry")}
          </button>
        </div>
      ) : (
        <>
          <ol className="mu-steps">
            <li>
              <span>{t("mu.step_open", { name: TARGET_NAME[p] })}</span>
              <span className="mu-step-btns">
                <button type="button" className="btn btn-primary" onClick={openPage}>
                  <Icon name="link" /> {t("mu.open_page", { name: TARGET_NAME[p] })}
                </button>
                {meta?.is_local && (
                  <button type="button" className="btn" onClick={openFolder}>
                    <Icon name="file" /> {t("mu.show_file")}
                  </button>
                )}
              </span>
            </li>
            <li>{t("mu.step_drop")}</li>
            <li>{t("mu.step_paste")}</li>
          </ol>
          {v.fixed.length > 0 && <p className="field-hint">{t("mu.fixed")}</p>}
          <CopyField label={t("mu.f_title")} value={v.texts.title} />
          <CopyField label={t("mu.f_description")} value={v.texts.description} rows={4} />
          <CopyField label={t("mu.f_hashtags")} value={v.texts.hashtags} />
          <label className="field">
            <span className="field-label">{t("mu.link")}</span>
            <input
              className="input"
              type="url"
              inputMode="url"
              placeholder="https://"
              value={link}
              onChange={(e) => setLink(e.target.value)}
            />
            <span className="field-hint">{t("mu.link_hint")}</span>
          </label>
        </>
      )}
    </Modal>
  );
}

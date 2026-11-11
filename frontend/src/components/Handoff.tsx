// 1.2.39: "Post it yourself" (semi-automatic, the default for Instagram and TikTok). After Publish,
// YouTube goes by itself; for Instagram and TikTok SharkyClips makes the file with the platform's
// preset, and this guide walks through them one after the other: "Copy & open" puts the caption +
// hashtags on the clipboard, shows the file and opens the upload page; then "Copied, paste and
// share" with the three steps, and "I shared it" moves on to the next platform.
import { useCallback, useEffect, useRef, useState } from "react";
import { copyText, platformsApi } from "../extras";
import { useI18n } from "../i18n";
import { publishApi, TARGET_NAME, type Handoff, type HandoffPlatform, type HandoffRequest, type Target } from "../multipost";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { PlatformIcon } from "./PlatformIcons";
import { Modal, ProgressBar } from "./ui";

type Step = "reels" | "tiktok";

/** Mounted once (App): opens when Publish hands platforms over (openHandoff). */
export function HandoffHost() {
  const [req, setReq] = useState<HandoffRequest | null>(null);
  useEffect(() => {
    const on = (e: Event) => setReq((e as CustomEvent<HandoffRequest>).detail);
    window.addEventListener("sc-handoff", on);
    return () => window.removeEventListener("sc-handoff", on);
  }, []);
  if (!req) return null;
  return <HandoffDialog key={`${req.pid}/${req.cid}`} req={req} onClose={() => setReq(null)} />;
}

function fileName(path: string | null): string {
  return (path ?? "").split(/[\\/]/).pop() ?? "";
}

const PASTE_KEYS = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘V" : "Ctrl+V";

function HandoffDialog({ req, onClose }: { req: HandoffRequest; onClose: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const steps = (["reels", "tiktok"] as Step[]).filter((p) => req.platforms.includes(p));
  const [data, setData] = useState<Handoff | null>(null);
  const [later, setLater] = useState<Step[]>([]);
  const [copied, setCopied] = useState<Partial<Record<Step, boolean | "failed">>>({});
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);

  const load = useCallback(() => {
    publishApi
      .handoff(req.pid, req.cid, steps)
      .then(setData)
      .catch(() => {});
  }, [req.pid, req.cid, steps.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(load, [load]);
  // poll while a file is still being made
  const making = steps.some((p) => {
    const s = data?.platforms[p]?.status;
    return !data || s === "preparing" || s === "uploading" || s === "idle" || s === "scheduled";
  });
  useEffect(() => {
    if (!making) return;
    timer.current = window.setTimeout(load, 1500);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [making, data, load]);

  const st = (p: Step): HandoffPlatform | undefined => data?.platforms[p];
  const done = (p: Step) => st(p)?.status === "published";
  const current = steps.find((p) => !done(p) && !later.includes(p)) ?? null;
  const next = current ? steps.slice(steps.indexOf(current) + 1).find((p) => !done(p) && !later.includes(p)) ?? null : null;

  const copyOpen = async (p: Step) => {
    const s = st(p);
    if (!s) return;
    // in the click itself: the browser allows the new tab and the clipboard
    const ok = await copyText(s.caption);
    window.open(s.upload_page, "_blank", "noopener");
    if (s.file) platformsApi.reveal(s.file).catch(() => {});
    setCopied((c) => ({ ...c, [p]: ok ? true : "failed" }));
  };
  const copyAgain = async (p: Step) => {
    const s = st(p);
    if (s && (await copyText(s.caption))) {
      setCopied((c) => ({ ...c, [p]: true }));
      toast({ kind: "ok", text: t("common.copied") });
    }
  };
  const sharedIt = async (p: Step) => {
    setBusy(true);
    try {
      setData(await publishApi.shared(req.pid, req.cid, p));
      window.dispatchEvent(new CustomEvent("sc-posts-changed"));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const retry = async (p: Step) => {
    try {
      await publishApi.retry(req.pid, req.cid, p as Target);
      load();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const allDone = steps.length > 0 && steps.every(done);
  const close = () => {
    window.dispatchEvent(new CustomEvent("sc-posts-changed"));
    onClose();
  };

  const body = (p: Step) => {
    const s = st(p);
    const name = TARGET_NAME[p];
    if (!s || s.status === "preparing" || s.status === "uploading" || s.status === "idle" || s.status === "scheduled") {
      return (
        <div className="ho-making">
          <p className="ho-line">
            <span className="spinner" /> {t("mp.ho_preparing", { name })}
            {s?.progress != null && ` ${num(Math.round(s.progress * 100))}%`}
          </p>
          <ProgressBar value={s?.progress ?? null} label={t("mp.ho_preparing", { name })} />
        </div>
      );
    }
    if (s.status === "failed" || s.status === "cancelled") {
      return (
        <div className="ho-fail" role="alert">
          <p className="ho-line">
            <Icon name="alert" size={16} /> {t("mp.ho_failed", { name })}
          </p>
          {s.error && (
            <p className="field-hint">
              {s.error.message} {s.error.hint}
            </p>
          )}
          <button type="button" className="btn" onClick={() => retry(p)}>
            <Icon name="refresh" /> {t("mp.ho_retry")}
          </button>
        </div>
      );
    }
    const c = copied[p];
    return (
      <div className="ho-ready">
        {s.remind_at && <p className="field-hint">{t("mp.ho_planned", { when: new Date(s.remind_at).toLocaleString() })}</p>}
        {!c ? (
          <>
            <button type="button" className={`btn btn-primary ez-big ho-go pf-accent-${p}`} onClick={() => copyOpen(p)}>
              <Icon name="copy" /> {t("mp.ho_copy_open", { name })}
            </button>
            <p className="field-hint">{t("mp.ho_copy_hint", { name })}</p>
          </>
        ) : (
          <>
            <div className={`ho-copied${c === "failed" ? " warn" : ""}`} role="status">
              <b>
                <Icon name={c === "failed" ? "alert" : "check"} size={18} /> {c === "failed" ? t("mp.ho_nocopy") : t("mp.ho_copied")}
              </b>
              <ol className="ho-steps">
                <li>
                  {t("mp.ho_step_file")} <span className="ho-file" dir="auto">{fileName(s.file)}</span>
                </li>
                <li>{t("mp.ho_step_paste", { keys: PASTE_KEYS })}</li>
                <li>{t("mp.ho_step_share", { name })}</li>
              </ol>
            </div>
            {s.ai_label && (
              <p className="ez-hint ai-remind" role="note">
                <Icon name="alert" size={14} /> {t(`platform.ai_remind.${p}`)}
              </p>
            )}
            <button type="button" className="btn btn-primary ez-big" disabled={busy} onClick={() => sharedIt(p)}>
              {busy ? <span className="spinner" /> : <Icon name="check" />}{" "}
              {next ? t("mp.ho_next", { name: TARGET_NAME[next] }) : t("mp.ho_done_btn")}
            </button>
            <div className="ho-tools">
              <button type="button" className="link-btn" onClick={() => copyAgain(p)}>
                <Icon name="copy" size={14} /> {t("mp.ho_copy_again")}
              </button>
              {s.file && (
                <button type="button" className="link-btn" onClick={() => platformsApi.reveal(s.file!).catch(() => {})}>
                  <Icon name="file" size={14} /> {t("mp.ho_show_file")}
                </button>
              )}
              <a className="link-btn" href={s.upload_page} target="_blank" rel="noreferrer">
                <Icon name="link" size={14} /> {t("mp.ho_open_again", { name })}
              </a>
            </div>
          </>
        )}
        <details className="ho-caption">
          <summary>{t("mp.ho_caption")}</summary>
          <textarea className="input" dir="auto" rows={5} readOnly value={s.caption} onFocus={(e) => e.currentTarget.select()} />
        </details>
      </div>
    );
  };

  return (
    <Modal
      top
      title={
        <span className="mp-title">
          <Icon name="upload" /> {t("mp.ho_title")}
          {req.title && <span className="mp-title-clip" dir="auto">{req.title}</span>}
        </span>
      }
      onClose={close}
      footer={
        <>
          {current && !allDone && (
            <button type="button" className="btn btn-ghost" onClick={() => setLater((l) => [...l, current])}>
              {t("mp.ho_skip")}
            </button>
          )}
          <button type="button" className={`btn${allDone || !current ? " btn-primary" : ""}`} onClick={close}>
            {t("common.close")}
          </button>
        </>
      }
    >
      <p className="field-hint ho-intro">{t("mp.ho_intro")}</p>
      <ol className="ho-track" aria-label={t("mp.ho_title")}>
        {steps.map((p, i) => {
          const s = st(p);
          const state = done(p) ? "done" : p === current ? "now" : later.includes(p) ? "later" : "wait";
          return (
            <li key={p} className={`ho-pill ho-${state} pf-accent-${p}`} aria-current={p === current ? "step" : undefined}>
              <span className="ho-num">{done(p) ? <Icon name="check" size={12} /> : num(i + 1)}</span>
              <PlatformIcon p={p} size={15} /> {TARGET_NAME[p]}
              <span className="ho-pill-st">
                {done(p)
                  ? t("mp.ho_shared")
                  : later.includes(p)
                    ? t("mp.ho_skipped")
                    : s?.status === "ready"
                      ? t("mp.st_ready")
                      : s?.status === "failed"
                        ? t("mp.st_failed")
                        : t("mp.ho_waiting")}
              </span>
            </li>
          );
        })}
      </ol>
      {current ? (
        <section className={`ho-card pf-accent-${current}`} aria-label={TARGET_NAME[current]}>
          <header className="ho-card-head">
            <PlatformIcon p={current} size={20} /> <b>{TARGET_NAME[current]}</b>
          </header>
          {body(current)}
        </section>
      ) : allDone ? (
        <div className="ho-all" role="status">
          <Icon name="check" size={22} /> <b>{t("mp.ho_all_done")}</b>
        </div>
      ) : (
        <p className="field-hint">{t("mp.ho_later_note")}</p>
      )}
    </Modal>
  );
}

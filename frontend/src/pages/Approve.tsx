import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, phoneApi, type ApproveClip } from "../api";
import { BrandMark } from "../components/Brand";
import { Icon } from "../components/Icons";
import { useI18n } from "../i18n";
import { useToast } from "../toast";

const SWIPE = 90; // px: a swipe this far decides

/** Phone approval page (#/approve, an installable web app on the Wi-Fi; PIN required there).
 * Swipe right = upload, left = skip; buttons do the same (and Plan). */
export default function Approve() {
  const { t, num } = useI18n();
  const toast = useToast();
  const [clips, setClips] = useState<ApproveClip[] | null>(null);
  const [youtube, setYoutube] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dx, setDx] = useState(0);
  const [leaving, setLeaving] = useState<"left" | "right" | null>(null);
  const [muted, setMuted] = useState(true);
  const start = useRef<{ x: number; y: number; id: number } | null>(null);

  const load = useCallback(
    () =>
      phoneApi
        .approve()
        .then((r) => {
          setClips(r.clips);
          setYoutube(r.youtube);
        })
        .catch(() => setClips((c) => c ?? [])),
    [],
  );
  useEffect(() => {
    load();
    const iv = window.setInterval(load, 30000);
    try {
      if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("/sw.js").catch(() => {});
    } catch {
      /* no service worker: still works as a page */
    }
    return () => window.clearInterval(iv);
  }, [load]);

  const cur = clips?.[0] ?? null;

  const act = useCallback(
    async (action: "upload" | "plan" | "skip") => {
      if (!cur || busy) return;
      if (action !== "skip" && !youtube) {
        toast({ kind: "err", text: t("approve.no_youtube") });
        setDx(0);
        return;
      }
      setBusy(true);
      setLeaving(action === "skip" ? "left" : "right");
      try {
        const r = await phoneApi.act(cur.project_id, cur.clip_id, action);
        toast({ kind: action === "skip" ? "info" : "ok", text: r.text });
        window.setTimeout(() => {
          setClips(r.clips);
          setLeaving(null);
          setDx(0);
        }, 220);
      } catch (e) {
        setLeaving(null);
        setDx(0);
        if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
      } finally {
        setBusy(false);
      }
    },
    [cur, busy, youtube, toast, t],
  );

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      const rtl = document.documentElement.dir === "rtl";
      if (e.key === "ArrowRight") act(rtl ? "skip" : "upload");
      if (e.key === "ArrowLeft") act(rtl ? "upload" : "skip");
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [act]);

  const onDown = (e: React.PointerEvent) => {
    if (busy || (e.target as HTMLElement).closest("button")) return;
    start.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
  };
  const onMove = (e: React.PointerEvent) => {
    const s = start.current;
    if (!s || s.id !== e.pointerId) return;
    const mx = e.clientX - s.x;
    if (Math.abs(mx) > 8 && Math.abs(mx) > Math.abs(e.clientY - s.y)) {
      (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
      setDx(mx);
    }
  };
  const onUp = () => {
    const d = dx;
    start.current = null;
    if (d > SWIPE) act("upload");
    else if (d < -SWIPE) act("skip");
    else setDx(0);
  };

  const shift = leaving === "right" ? 600 : leaving === "left" ? -600 : dx;
  const hint = dx > 30 ? "upload" : dx < -30 ? "skip" : null;

  return (
    <main className="approve" aria-labelledby="approve-title">
      <header className="approve-head">
        <span className="brand-mark" aria-hidden="true">
          <BrandMark />
        </span>
        <h1 id="approve-title">{t("approve.title")}</h1>
        {clips && clips.length > 0 && <span className="chip">{t("approve.left", { n: clips.length })}</span>}
      </header>

      {!youtube && (
        <p className="notice approve-note">
          <Icon name="alert" />
          <span>{t("approve.no_youtube")}</span>
        </p>
      )}

      {clips === null ? (
        <p className="muted approve-empty">{t("common.loading")}</p>
      ) : !cur ? (
        <div className="approve-empty">
          <Icon name="check" size={40} />
          <h2>{t("approve.empty_title")}</h2>
          <p className="muted">{t("approve.empty_body")}</p>
          <button className="btn" onClick={load}>
            <Icon name="refresh" size={14} /> {t("approve.refresh")}
          </button>
        </div>
      ) : (
        <>
          <div className="approve-stack">
            {clips[1] && <div className="approve-card approve-under" aria-hidden="true" />}
            <article
              key={`${cur.project_id}/${cur.clip_id}`}
              className={`approve-card${leaving ? " leaving" : ""}${hint ? ` hint-${hint}` : ""}`}
              style={{ transform: `translateX(${shift}px) rotate(${shift / 30}deg)` }}
              onPointerDown={onDown}
              onPointerMove={onMove}
              onPointerUp={onUp}
              onPointerCancel={onUp}
              aria-label={cur.title}
            >
              <video
                src={cur.video}
                autoPlay
                loop
                playsInline
                muted={muted}
                preload="metadata"
                onClick={() => setMuted((m) => !m)}
              />
              <button className="approve-sound btn btn-sm" onClick={() => setMuted((m) => !m)} aria-pressed={!muted}>
                {muted ? t("approve.sound_on") : t("approve.sound_off")}
              </button>
              {hint && <span className={`approve-stamp ${hint}`}>{hint === "upload" ? t("approve.upload") : t("approve.skip")}</span>}
              <div className="approve-info">
                <h2>{cur.title}</h2>
                <div className="approve-meta">
                  {cur.viral_score != null && (
                    <span className="chip chip-gold">
                      {t("approve.viral", { label: cur.viral_label ?? "", n: num(cur.viral_score) })}
                    </span>
                  )}
                  {cur.marked && <span className="chip">{t("approve.marked")}</span>}
                  <span className="muted">{cur.project_title}</span>
                </div>
              </div>
            </article>
          </div>
          <div className="approve-actions">
            <button className="btn btn-lg approve-skip" disabled={busy} onClick={() => act("skip")}>
              <Icon name="x" /> {t("approve.skip")}
            </button>
            <button className="btn btn-lg" disabled={busy || !youtube} onClick={() => act("plan")}>
              <Icon name="calendar" /> {t("approve.plan")}
            </button>
            <button className="btn btn-lg btn-primary" disabled={busy || !youtube} onClick={() => act("upload")}>
              <Icon name="upload" /> {t("approve.upload")}
            </button>
          </div>
          <p className="muted approve-tip">{t("approve.tip")}</p>
        </>
      )}
    </main>
  );
}

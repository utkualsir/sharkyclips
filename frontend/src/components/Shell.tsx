import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { api, setHeavyGuard, ApiError, type ChangelogEntry } from "../api";
import { useAppState } from "../appstate";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";
import { Modal, Sep } from "./ui";
import versionFile from "../../../VERSION?raw";

/** The version these UI files were built from (the one VERSION file). */
const UI_VERSION = versionFile.trim();

// ---------------------------------------------------------------- tiny markdown (CHANGELOG.md)

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const s = m[0];
    if (s.startsWith("**")) out.push(<strong key={k++}>{s.slice(2, -2)}</strong>);
    else if (s.startsWith("`")) out.push(<code key={k++}>{s.slice(1, -1)}</code>);
    else {
      const [, label, href] = /\[([^\]]+)\]\(([^)]+)\)/.exec(s)!;
      out.push(
        <a key={k++} href={href} target="_blank" rel="noreferrer">
          {label}
        </a>,
      );
    }
    last = m.index + s.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Headings (###), bullet lists (- , nested by indent), paragraphs, **bold**, `code`, [links](). */
export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r/g, "").split("\n");
  let para: string[] = [];
  let items: { depth: number; text: string }[] = [];
  const flushPara = () => {
    if (para.length) blocks.push(<p key={blocks.length}>{inline(para.join(" "))}</p>);
    para = [];
  };
  const flushList = () => {
    if (!items.length) return;
    const top: { text: string; sub: string[] }[] = [];
    for (const it of items) {
      if (it.depth > 0 && top.length) top[top.length - 1].sub.push(it.text);
      else top.push({ text: it.text, sub: [] });
    }
    blocks.push(
      <ul key={blocks.length}>
        {top.map((it, i) => (
          <li key={i}>
            {inline(it.text)}
            {it.sub.length > 0 && (
              <ul>
                {it.sub.map((s, j) => (
                  <li key={j}>{inline(s)}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>,
    );
    items = [];
  };
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    const h = /^(#{2,4})\s+(.*)$/.exec(line);
    const li = /^(\s*)[-*]\s+(.*)$/.exec(line);
    if (!line.trim() || /^<!--.*-->$/.test(line.trim())) {
      flushPara();
      flushList();
    } else if (h) {
      flushPara();
      flushList();
      blocks.push(<h3 key={blocks.length}>{inline(h[2])}</h3>);
    } else if (li) {
      flushPara();
      items.push({ depth: li[1].length >= 2 ? 1 : 0, text: li[2] });
    } else if (items.length && /^\s+/.test(line)) {
      items[items.length - 1].text += " " + line.trim(); // wrapped bullet line
    } else {
      flushList();
      para.push(line.trim());
    }
  }
  flushPara();
  flushList();
  return <div className="md">{blocks.map((b, i) => <Fragment key={i}>{b}</Fragment>)}</div>;
}

// ---------------------------------------------------------------- what's new

/** "What's new in 1.2.1": once after an update (or from the footer), in the UI language. */
export function WhatsNew({ version, onClose }: { version: string; onClose: () => void }) {
  const { t, lang } = useI18n();
  const [entry, setEntry] = useState<ChangelogEntry | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    api.changelog(version, lang).then(setEntry).catch(() => setFailed(true));
  }, [version, lang]);
  if (failed) return null;
  return (
    <Modal
      title={t("whatsnew.title", { v: version })}
      onClose={onClose}
      footer={
        <button className="btn btn-primary" onClick={onClose}>
          {t("whatsnew.ok")}
        </button>
      }
    >
      {entry ? (
        <div className="whatsnew" tabIndex={0} role="region" aria-label={t("whatsnew.title", { v: version })} lang={entry.lang} dir={entry.lang === "ar" ? "rtl" : "ltr"}>
          <Markdown text={entry.markdown} />
        </div>
      ) : (
        <div className="skeleton-lines">
          {[70, 90, 55, 80, 40].map((w) => (
            <div key={w} className="skeleton" style={{ width: `${w}%` }} />
          ))}
        </div>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- dev banner

function fmtStart(iso: string, lang: string): string {
  const d = new Date(iso);
  const sameDay = d.toDateString() === new Date().toDateString();
  return new Intl.DateTimeFormat(`${lang}-u-nu-latn`, sameDay ? { timeStyle: "short" } : { dateStyle: "medium", timeStyle: "short" }).format(d);
}

/** "Update in progress - under construction" on every screen while the dev flag is fresh.
 * Also asks before heavy jobs start while it is up. */
export function DevBanner() {
  const { t, lang } = useI18n();
  const { state } = useAppState();
  const dev = state?.dev ?? null;
  const [asking, setAsking] = useState<null | ((ok: boolean) => void)>(null);
  const devRef = useRef(dev);
  devRef.current = dev;

  useEffect(() => {
    setHeavyGuard(
      () =>
        new Promise<void>((resolve, reject) => {
          if (!devRef.current) return resolve();
          setAsking(() => (ok: boolean) => {
            setAsking(null);
            if (ok) resolve();
            else reject(new ApiError(t("dev.not_started"), null, 0));
          });
        }),
    );
    return () => setHeavyGuard(null);
  }, [t]);

  return (
    <>
      {dev && (
        <div className="dev-banner" role="status">
          <Icon name="settings" size={15} />
          <span className="dev-banner-text">
            <b>{t("dev.banner")}</b>
            {dev.task && <span className="dev-banner-task"><Sep />{dev.task}</span>}
            <span className="dev-banner-time"><Sep />{t("dev.since", { time: fmtStart(dev.started_at, lang) })}</span>
          </span>
        </div>
      )}
      {asking && (
        <Modal
          top
          title={t("dev.confirm_title")}
          onClose={() => asking(false)}
          footer={
            <>
              <button className="btn" onClick={() => asking(false)}>
                {t("dev.confirm_cancel")}
              </button>
              <button className="btn btn-primary" onClick={() => asking(true)}>
                {t("dev.confirm_ok")}
              </button>
            </>
          }
        >
          <p style={{ margin: 0 }}>{t("dev.confirm_body")}</p>
        </Modal>
      )}
    </>
  );
}

// ---------------------------------------------------------------- stale server

/** "1.2.10" -> [1, 2, 10]: compared as numbers, never as text. */
export function versionParts(v: string | null | undefined): number[] {
  const n = String(v ?? "").match(/\d+/g)?.slice(0, 3).map(Number) ?? [];
  while (n.length < 3) n.push(0);
  return n;
}

/** True only when `a` is a strictly higher version than `b`. */
export function isNewer(a: string | null | undefined, b: string | null | undefined): boolean {
  if (!a || !b) return false;
  const x = versionParts(a);
  const y = versionParts(b);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i];
  return false;
}

/** The files on disk are a NEWER version than the server answering (an old SharkyClips kept
 * running through an update): offer the restart that finishes the update.
 * 1.2.51: the server decides (`restart_needed`: its loaded code vs. the VERSION file now), never
 * a version baked into these UI files at build time (a build made before the version bump said
 * "updated to 1.2.49, the old 1.2.50 still runs" and the restart could never make it go away).
 * Equal or lower = no bar. A restart that doesn't bring the new version within 45 s, or the ×,
 * hides the bar for this version and the app goes on with the running one (no loop). */
const STALE_WAIT_MS = 45_000;
const dismissKey = (v: string) => `sharkyclips.stale-dismissed.${v}`;

export function StaleServerBar() {
  const { t } = useI18n();
  const { state, refresh } = useAppState();
  const [phase, setPhase] = useState<"idle" | "restarting" | "manual" | "hidden">("idle");
  const server = state?.version;
  // An older server (before 1.2.51) has no restart_needed: then the UI build may only win upward.
  const disk = state ? (state.disk_version ?? (isNewer(UI_VERSION, server) ? UI_VERSION : null)) : null;
  const stale = !!server && !!disk && (state?.restart_needed ?? isNewer(disk, server));
  const dismissed = (() => {
    try {
      return !!disk && window.sessionStorage.getItem(dismissKey(disk)) === "1";
    } catch {
      return false;
    }
  })();
  const hide = () => {
    try {
      if (disk) window.sessionStorage.setItem(dismissKey(disk), "1");
    } catch {
      /* private mode: hidden for this page view only */
    }
    setPhase("hidden");
  };
  useEffect(() => {
    if (phase !== "restarting") return;
    if (!stale) return window.location.reload(); // the new server answers
    const id = window.setInterval(refresh, 1000); // until the new server answers
    const give = window.setTimeout(hide, STALE_WAIT_MS); // never wait forever
    return () => {
      window.clearInterval(id);
      window.clearTimeout(give);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, stale, refresh]);
  if (!stale || dismissed || phase === "hidden") return null;
  const restart = () =>
    api
      .updateRestart()
      .then((r) => setPhase(r.restarting ? "restarting" : "manual"))
      .catch(() => setPhase("manual"));
  return (
    <div className="dev-banner stale-bar" role="status">
      <Icon name="alert" size={15} />
      <span className="dev-banner-text">
        <b>{t("stale.banner", { ui: disk ?? "", server })}</b>{" "}
        {phase === "manual" && <span className="dev-banner-task">{t("stale.manual")}</span>}
      </span>
      {phase !== "manual" && (
        <button className="btn btn-sm" onClick={restart} disabled={phase === "restarting"}>
          {t(phase === "restarting" ? "stale.restarting" : "stale.restart")}
        </button>
      )}
      <button className="btn btn-sm btn-ghost" onClick={hide} aria-label={t("stale.dismiss")} title={t("stale.dismiss")}>
        <Icon name="x" size={14} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------- footer

export function Footer({ onWhatsNew }: { onWhatsNew: () => void }) {
  const { t } = useI18n();
  const { state } = useAppState();
  if (!state) return null;
  return (
    <footer className="app-footer">
      <span>
        SharkyClips <span className="mono">{state.version}</span>
      </span>
      <Sep />
      <button className="link-btn" onClick={onWhatsNew}>
        {t("whatsnew.link")}
      </button>
      <Sep />
      <a className="link-btn" href="#/updates">
        {t("updates.open")}
      </a>
    </footer>
  );
}

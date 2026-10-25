import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { api, setHeavyGuard, ApiError, type ChangelogEntry } from "../api";
import { useAppState } from "../appstate";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";
import { Modal } from "./ui";

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
      blocks.push(<h4 key={blocks.length}>{inline(h[2])}</h4>);
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
        <div className="whatsnew" lang={entry.lang} dir={entry.lang === "ar" ? "rtl" : "ltr"}>
          <Markdown text={entry.markdown} />
        </div>
      ) : (
        <div className="notice">
          <span className="spinner" />
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
            {dev.task && <span className="dev-banner-task"> · {dev.task}</span>}
            <span className="dev-banner-time"> · {t("dev.since", { time: fmtStart(dev.started_at, lang) })}</span>
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
      <span aria-hidden="true">·</span>
      <button className="link-btn" onClick={onWhatsNew}>
        {t("whatsnew.link")}
      </button>
    </footer>
  );
}

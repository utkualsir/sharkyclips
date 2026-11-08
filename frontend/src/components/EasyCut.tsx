import { useEffect, useRef, useState } from "react";
import { ApiError, easyApi, type CaptionWord, type EasyClip, type EasyHook, type EasyView, type NudgeAction } from "../api";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Icon, type IconName } from "./Icons";

/** Easy 2.0 (1.2.34): what the smart cut did + one-tap nudges (start earlier, end later,
 *  short / long version, back to the smart cut). */
export function CutRow({ pid, c, disabled, onView }: { pid: string; c: EasyClip; disabled: boolean; onView: (v: EasyView) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState<NudgeAction | null>(null);
  const sh = c.shape;
  if (!sh) return null;

  const run = async (a: NudgeAction) => {
    setBusy(a);
    try {
      onView(await easyApi.nudge(pid, c.id, a));
      toast({ kind: "ok", text: t("easy2.nudged"), hint: t("easy.saved_rerender") });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(null);
    }
  };

  const why = sh.why.slice(0, 2);
  const btn = (a: NudgeAction, icon: IconName, label: string) => (
    <button type="button" className="ez-nudge" onClick={() => run(a)} disabled={disabled || busy !== null}>
      {busy === a ? <span className="spinner" /> : <Icon name={icon} size={14} />}
      <span>{label}</span>
    </button>
  );

  return (
    <div className="ez-cut">
      {sh.hook && <HookChip h={sh.hook} />}
      {why.length > 0 && (
        <p className="ez-cut-why">
          <Icon name="scissors" size={14} />
          <span>{why.map((w) => t(`easy2.why_${w}`)).join(" · ")}</span>
        </p>
      )}
      {sh.length && (
        <p className={`ez-cut-len${sh.length === "very_long" ? " warn" : ""}`}>
          <Icon name="alert" size={14} />
          <span>
            {t(`easy2.len_${sh.length}`, { s: num(Math.round(c.duration)), max: num(sh.target.max) })}
          </span>
        </p>
      )}
      <div className="ez-nudges" role="group" aria-label={t("easy2.nudge_group")}>
        {btn("earlier", "chevron-left", t("easy2.earlier"))}
        {btn("later", "chevron-right", t("easy2.later"))}
        {btn("short", "minus", t("easy2.short"))}
        {btn("long", "plus", t("easy2.long"))}
        {!sh.auto && sh.shaped && btn("auto", "sparkles", t("easy2.back_auto"))}
      </div>
    </div>
  );
}

/** Older projects: one tap switches the smart cuts on. */
export function SmartBanner({ pid, onView }: { pid: string; onView: (v: EasyView) => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <div className="notice ez-smart" role="note">
      <Icon name="sparkles" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="notice-title">{t("easy2.smart_title")}</div>
        <div className="muted">{t("easy2.smart_body")}</div>
      </div>
      <button
        className="btn btn-primary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            onView(await easyApi.smart(pid, true));
          } catch (e) {
            if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy && <span className="spinner" />} {t("easy2.smart_on")}
      </button>
    </div>
  );
}

/** The hook check: score of the first 3 seconds, and what was done when it was weak. */
function HookChip({ h }: { h: EasyHook }) {
  const { t, num } = useI18n();
  const level = h.score >= 65 ? "strong" : h.score >= 52 ? "ok" : "weak";
  const better = h.score > h.before + 0.5;
  return (
    <p className={`ez-hook ez-hook-${level}`}>
      <Icon name="zap" size={14} />
      <span>
        <b>{better ? t("easy2.hook_better", { a: num(h.before), b: num(h.score) }) : t("easy2.hook_score", { n: num(h.score) })}</b>
        {" · "}
        {h.choice === "flash" ? t("easy2.hook_flash") : h.choice === "later" ? t("easy2.hook_later", { s: num(h.moved, 1) }) : t(`easy2.hook_${level}`)}
      </span>
    </p>
  );
}

/** Why this clip: the viral label (or, once it's live, the real views) + 1-3 plain reasons. */
export function ReasonChips({ c, children }: { c: EasyClip; children?: React.ReactNode }) {
  const { t, lang } = useI18n();
  const views = c.upload?.views;
  const live = views != null && (c.upload.status === "published" || c.upload.status === "locked");
  const compact = (n: number) => new Intl.NumberFormat(`${lang}-u-nu-latn`, { notation: "compact", maximumFractionDigits: 1 }).format(n);
  const label = (ch: { code: string; value?: string; count?: number }) => {
    const base = t(`reason.${ch.code}`);
    if (ch.code === "keyword" && ch.value) return `“${ch.value}”`;
    if (ch.code === "df_multikill" && ch.value) return `${base} ×${ch.value}`;
    if (ch.count && ch.count > 1 && !ch.code.startsWith("lol_")) return `${base} ×${ch.count}`;
    return base;
  };
  return (
    <div className="ez-chips">
      {live ? (
        <span className="ez-viral ez-viral-real">
          <Icon name="eye" size={13} /> {t("easy2.real_views", { n: compact(views!) })}
        </span>
      ) : (
        c.viral_label && (
          <span className={`ez-viral ez-viral-${c.viral_label}`}>
            <Icon name="sparkles" size={13} /> {t("easy.viral", { label: t(`publish.label.${c.viral_label}`) })}
          </span>
        )
      )}
      {(c.taste ?? 0) >= 0.35 && (
        <span className="ez-chip ez-chip-taste">
          <Icon name="thumb-up" size={12} /> {t("easy2.your_taste")}
        </span>
      )}
      {(c.chips ?? []).map((ch) => (
        <span key={ch.code} className="ez-chip" dir="auto">
          {label(ch)}
        </span>
      ))}
      {children}
    </div>
  );
}

/** 👍 / 👎 on the whole clip: future picks learn what the creator likes. */
export function TasteButtons({ pid, c, need, onView, onDiscard }: { pid: string; c: EasyClip; need: number; onView: (v: EasyView) => void; onDiscard: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const cur = c.vote ?? 0;
  const send = async (v: number) => {
    const value = cur === v ? 0 : v;
    setBusy(true);
    try {
      const nv = await easyApi.vote(pid, c.id, value);
      onView(nv);
      if (value !== 0) {
        const left = nv.taste?.need ?? 0;
        toast({
          kind: "ok",
          text: value > 0 ? t("easy2.liked") : t("easy2.disliked"),
          hint: left > 0 ? t("easy2.taste_need", { n: num(left) }) : t("easy2.taste_on"),
          action: value < 0 ? { label: t("easy.discard"), run: onDiscard } : undefined,
        });
      }
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="ez-taste" role="group" aria-label={t("easy2.taste_group")} title={need > 0 ? t("easy2.taste_need", { n: num(need) }) : undefined}>
      <button type="button" className={`btn btn-ghost icon-btn ez-thumb${cur > 0 ? " on" : ""}`} aria-pressed={cur > 0} aria-label={t("easy2.like")} disabled={busy} onClick={() => send(1)}>
        <Icon name="thumb-up" size={16} />
      </button>
      <button type="button" className={`btn btn-ghost icon-btn ez-thumb${cur < 0 ? " on bad" : ""}`} aria-pressed={cur < 0} aria-label={t("easy2.dislike")} disabled={busy} onClick={() => send(-1)}>
        <Icon name="thumb-down" size={16} />
      </button>
    </div>
  );
}

/** 1.2.34: tap a wrong caption word, type it right. The clip is made again and the mistake is
 *  remembered for every later clip (new names / game words go into the glossary). */
export function CaptionFixer({ pid, cid, onChanged }: { pid: string; cid: string; onChanged: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [words, setWords] = useState<CaptionWord[] | null>(null);
  const [edit, setEdit] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    easyApi.captions(pid, cid).then((r) => setWords(r.words)).catch(() => setWords([]));
  }, [pid, cid]);
  useEffect(() => {
    if (edit) input.current?.select();
  }, [edit]);

  const save = async (w: CaptionWord) => {
    const v = text.trim();
    setEdit(null);
    if (!v || v === w.word) return;
    setBusy(true);
    try {
      const r = await easyApi.fixCaption(pid, cid, w.key, v);
      setWords(r.words);
      onChanged();
      toast({
        kind: "ok",
        text: t("easy2.cap_fixed"),
        hint: r.learned ? t(r.learned.glossary ? "easy2.cap_learned_glossary" : "easy2.cap_learned", { a: r.learned.from, b: r.learned.to }) : null,
      });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(false);
    }
  };

  if (words === null) return <div className="skeleton" style={{ height: 60 }} />;
  if (!words.length) return <p className="muted">{t("easy2.cap_none")}</p>;
  return (
    <div className={`ez-capfix${busy ? " busy" : ""}`} aria-busy={busy}>
      {words.map((w) =>
        edit === w.key ? (
          <input
            key={w.key}
            ref={input}
            className="input ez-capfix-input"
            dir="auto"
            value={text}
            maxLength={40}
            size={Math.max(4, text.length + 1)}
            aria-label={t("easy2.cap_edit", { w: w.word })}
            onChange={(e) => setText(e.target.value)}
            onBlur={() => save(w)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                save(w);
              } else if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                setEdit(null);
              }
            }}
          />
        ) : (
          <button
            key={w.key}
            type="button"
            className={`ez-capword${w.mine ? " mine" : ""}${w.swear ? " swear" : ""}`}
            dir="auto"
            disabled={w.swear || busy}
            aria-label={w.swear ? t("easy2.cap_swear") : t("easy2.cap_edit", { w: w.word })}
            onClick={() => {
              setText(w.word);
              setEdit(w.key);
            }}
          >
            {w.word}
          </button>
        ),
      )}
    </div>
  );
}

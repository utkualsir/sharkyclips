// 1.2.66 "Share clips" board, 1.2.68 "share now" (the same board in Easy and Pro mode):
// every clip in one big grid -> tick YouTube / Instagram / TikTok -> Share. Everything goes now,
// up to what YouTube really allows today; for more, a choice: by hand now, or tomorrow / a day you
// pick. Every card can also be uploaded by hand. Already-shared warning, video language and
// "Free up space" live on the same screen.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, urls } from "../api";
import { fmtTime } from "../format";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { publishApi, TARGET_NAME, type Target } from "../multipost";
import { href } from "../router";
import {
  gb,
  shareApi,
  shareChanged,
  whenText,
  type Batch,
  type Overflow,
  type ShareBoard,
  type ShareBody,
  type ShareCard,
  type ShareKind,
  type SharePlan,
} from "../share";
import { useToast } from "../toast";
import { useMeta } from "../meta";
import { Icon } from "../components/Icons";
import { PlatformIcon } from "../components/PlatformIcons";
import { Modal, ProgressBar } from "../components/ui";
import { ShareFlow } from "../components/ShareFlow";
import { UploadsLeft } from "../components/UploadsLeft";
import { ManualUpload } from "../components/ManualUpload";
import { AlreadyShared } from "../components/SharedBefore";
import { ConnectDialog, accountsChanged } from "../components/Accounts";
import { problemText } from "../components/PublishAll";

type Filter = "all" | "not_shared" | "shared";
const ORDER: Target[] = ["youtube", "reels", "tiktok"];
const UNDO_MS = 8000;
const AUTO_FIX = ["shorten_title", "shorten_description", "shorten_caption", "trim_hashtags", "vary_caption"];

/** Cards that count as "shared" for the filter and the dimming: out on at least one platform. */
const isShared = (c: ShareCard) => c.status.shared.length > 0;

export default function ShareClips({ id }: { id: string }) {
  const { t } = useI18n();
  return (
    <main className="page share-page">
      <a className="crumbs" href={href.project(id)}>
        <Icon name="chevron-left" className="icon flip-rtl" />
        <span>{t("share.back_project")}</span>
      </a>
      <ShareBoardView id={id} />
    </main>
  );
}

/** The board itself: the Share page (Pro) and the Easy project page both show this. */
export function ShareBoardView({ id, easy = false, onMissing }: { id: string; easy?: boolean; onMissing?: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [board, setBoard] = useState<ShareBoard | null>(null);
  const [missing, setMissing] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [sel, setSel] = useState<string[]>([]);
  const [targets, setTargets] = useState<Target[] | null>(null);
  const [flow, setFlow] = useState<string[] | null>(null);
  const [confirm, setConfirm] = useState<{ body: ShareBody; plan: SharePlan } | null>(null);
  const [manual, setManual] = useState<{ cid: string; title: string; platform: Target } | null>(null);
  const [connect, setConnect] = useState<Target | null>(null);
  const [freeOpen, setFreeOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [playing, setPlaying] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, number>>({}); // cid -> undo timer
  const pendingRef = useRef(pending);
  pendingRef.current = pending;

  const load = useCallback(() => {
    shareApi
      .board(id)
      .then((b) => {
        setBoard(b);
        setTargets((cur) => cur ?? initialTargets(b));
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) {
          setMissing(true);
          onMissing?.();
        }
      });
  }, [id, onMissing]);
  useEffect(() => load(), [load]);
  useEffect(() => {
    window.addEventListener("sc-share-changed", load);
    return () => window.removeEventListener("sc-share-changed", load);
  }, [load]);

  const moving =
    !!board &&
    (board.batch?.state === "running" ||
      board.clips.some((c) => c.status.kind === "working" || c.status.waits.length > 0));
  useEffect(() => {
    const iv = window.setInterval(() => document.visibilityState === "visible" && load(), moving ? 2000 : 15000);
    return () => window.clearInterval(iv);
  }, [load, moving]);

  // unschedule waits UNDO_MS with Undo; leaving the page sends it at once
  const commitUnschedule = useCallback(
    (cids: string[]) => {
      shareApi
        .unschedule(id, cids)
        .then((r) => {
          if (r.errors.length) toast({ kind: "err", text: r.errors[0].message });
          shareChanged();
          load();
        })
        .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
    },
    [id, load, toast],
  );
  useEffect(
    () => () => {
      const left = Object.keys(pendingRef.current);
      for (const tm of Object.values(pendingRef.current)) window.clearTimeout(tm);
      if (left.length) shareApi.unschedule(id, left).then(shareChanged).catch(() => {});
    },
    [id],
  );
  const unschedule = (cids: string[]) => {
    const tm = window.setTimeout(() => {
      setPending((p) => {
        const n = { ...p };
        for (const c of cids) delete n[c];
        return n;
      });
      commitUnschedule(cids);
    }, UNDO_MS);
    setPending((p) => ({ ...p, ...Object.fromEntries(cids.map((c) => [c, tm])) }));
    toast({
      kind: "info",
      text: t("share.unscheduled", { n: cids.length }),
      hint: t("share.undo_hint"),
      ms: UNDO_MS,
      action: {
        label: t("share.undo"),
        run: () => {
          window.clearTimeout(tm);
          setPending((p) => {
            const n = { ...p };
            for (const c of cids) delete n[c];
            return n;
          });
        },
      },
    });
  };

  const retry = (cids: string[]) =>
    shareApi
      .retry(id, cids)
      .then((r) => {
        if (r.errors.length) toast({ kind: "err", text: r.errors[0].message, hint: r.errors[0].hint });
        else toast({ kind: "ok", text: t("share.retrying", { n: cids.length }) });
        load();
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));

  const clips = useMemo(() => board?.clips ?? [], [board]);
  const counts = useMemo(
    () => ({
      all: clips.length,
      not_shared: clips.filter((c) => !isShared(c)).length,
      shared: clips.filter(isShared).length,
    }),
    [clips],
  );
  const shown = clips.filter((c) => (filter === "all" ? true : filter === "shared" ? isShared(c) : !isShared(c)));
  const toggle = (cid: string) => setSel((s) => (s.includes(cid) ? s.filter((x) => x !== cid) : [...s, cid]));
  const notShared = clips.filter((c) => c.status.kind === "not_shared").map((c) => c.id);

  // keyboard: Esc clears the selection, Ctrl+A picks every clip shown
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (flow || confirm || manual || document.querySelector('[aria-modal="true"]')) return;
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable || el.tagName === "SELECT")) {
        if (!(el.tagName === "INPUT" && (el as HTMLInputElement).type === "checkbox")) return;
      }
      if (e.key === "Escape" && sel.length) {
        e.preventDefault();
        setSel([]);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        e.preventDefault();
        setSel(shown.map((c) => c.id));
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  });

  // ---------------------------------------------------------------- share (plan -> choice? -> publish)
  const publish = (body: ShareBody, count: number) => {
    setBusy(true);
    return shareApi
      .publish(id, body)
      .then((r) => {
        toast({ kind: "ok", text: t("share.started_now", { n: num(r.plan.count || count) }), hint: t("share.started_hint") });
        setConfirm(null);
        setSel([]);
        shareChanged();
        load();
      })
      .catch((e) => {
        toast({ kind: "err", text: e.message, hint: e.hint });
        if (e instanceof ApiError && e.code === "problems" && !easy) setFlow(body.clips);
      })
      .finally(() => setBusy(false));
  };

  const share = async (cids: string[]) => {
    if (!board || !cids.length) return;
    const tg = (targets ?? []).filter((p) => board.platforms[p].usable);
    if (!tg.length) {
      toast({ kind: "info", text: t("share.pick_platform") });
      return;
    }
    setBusy(true);
    const body: ShareBody = { clips: cids, platforms: tg, consent: false };
    try {
      let plan = await shareApi.plan(id, body);
      // one-tap fixes the server can make by itself (a title too long, too many hashtags ...)
      const fixable = plan.rows.flatMap((r) =>
        r.problems.filter((x) => x.fix && AUTO_FIX.includes(x.fix)).map((x) => ({ cid: r.clip_id, x })),
      );
      if (fixable.length) {
        for (const f of fixable) await publishApi.fix(id, f.cid, f.x.platform, f.x.fix!).catch(() => {});
        plan = await shareApi.plan(id, body);
      }
      if (plan.count === 0) {
        toast({ kind: "info", text: t("share.nothing_new"), hint: t("share.nothing_new_hint") });
        return;
      }
      const ask = plan.over > 0 || plan.warnings > 0 || plan.needs_consent || plan.problems > 0 || plan.skipped > 0;
      if (ask) setConfirm({ body, plan });
      else await publish(body, plan.count);
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(false);
    }
  };

  if (missing) {
    return (
      <div className="empty">
        <h1 className="display">{t("project.not_found")}</h1>
        <a className="btn" href={href.library}>
          {t("nav.library")}
        </a>
      </div>
    );
  }
  if (!board || !targets) {
    return (
      <div className="empty">
        <span className="spinner" />
      </div>
    );
  }

  const batch = board.batch && !board.batch.dismissed ? board.batch : null;
  const goIds = sel.length ? sel : notShared;
  const plats = board.platforms;
  const flip = (p: Target) =>
    setTargets((ts) => {
      const cur = ts ?? [];
      return cur.includes(p) ? cur.filter((x) => x !== p) : ORDER.filter((x) => x === p || cur.includes(x));
    });

  return (
    <div className={`share-board${easy ? " is-easy" : ""}`}>
      <div className="share-head">
        <div style={{ minWidth: 0 }}>
          <h1 className="display" dir="auto">
            {easy ? board.title : t("share.title")}
          </h1>
          <p className="muted share-lede">{t("share.lede_now")}</p>
        </div>
        <div className="share-head-side">
          <UploadsLeft value={board.limit} big />
          <LanguagePick pid={id} value={board.language} onChanged={load} />
        </div>
      </div>

      {board.history?.before && <AlreadyShared h={board.history.before} />}
      {batch && <BatchPanel pid={id} batch={batch} clips={clips} onChanged={load} onUnschedule={unschedule} />}

      <section className="share-where" aria-label={t("share.step_where_short")}>
        <span className="share-where-label">{t("share.where_short")}</span>
        <div className="share-where-plats" role="group" aria-label={t("mp.where")}>
          {ORDER.map((p) => {
            const pl = plats[p];
            const on = targets.includes(p) && pl.usable;
            if (!pl.usable)
              return (
                <button key={p} type="button" className="share-chip is-off" onClick={() => setConnect(p)}>
                  <PlatformIcon p={p} size={18} />
                  <span>{TARGET_NAME[p]}</span>
                  <span className="muted share-chip-mode">{t("share.connect")}</span>
                </button>
              );
            return (
              <button
                key={p}
                type="button"
                className={`share-chip${on ? " is-on" : ""}`}
                aria-pressed={on}
                onClick={() => flip(p)}
                title={pl.auto_note ? t(`share.note_${pl.auto_note}`) : undefined}
              >
                <span className="share-chip-box" aria-hidden="true">
                  {on && <Icon name="check" size={13} />}
                </span>
                <PlatformIcon p={p} size={18} />
                <span>{TARGET_NAME[p]}</span>
                <span className="muted share-chip-mode">{pl.by_hand ? t("share.mode_by_hand") : t("share.mode_auto")}</span>
              </button>
            );
          })}
        </div>
        <button
          type="button"
          className="btn btn-primary btn-lg share-go"
          onClick={() => share(goIds)}
          disabled={busy || !goIds.length || !targets.some((p) => plats[p].usable)}
        >
          {busy ? <span className="spinner" /> : <Icon name="upload" />}{" "}
          {sel.length ? t("share.share_selected", { n: num(sel.length) }) : t("share.share_all", { n: num(goIds.length) })}
        </button>
        {!easy && sel.length > 0 && (
          <button type="button" className="btn" data-testid="share-review" onClick={() => setFlow(sel)}>
            <Icon name="list" /> {t("share.review_edit")}
          </button>
        )}
        {targets.filter((p) => plats[p].usable && plats[p].auto_note).length > 0 && (
          <p className="field-hint share-where-note">
            {targets
              .filter((p) => plats[p].usable && plats[p].auto_note)
              .map((p) => t(`share.note_${plats[p].auto_note}`))
              .join(" ")}
          </p>
        )}
      </section>

      <div className="share-toolbar">
        <div className="share-tabs" role="group" aria-label={t("share.filter")}>
          {(["all", "not_shared", "shared"] as Filter[]).map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {t(`share.filter_${f}`)} <span className="share-count mono">{num(counts[f])}</span>
            </button>
          ))}
        </div>
        <div className="share-selbtns">
          <button type="button" className="btn" onClick={() => setSel(shown.map((c) => c.id))} disabled={!shown.length}>
            <Icon name="check" /> {t("share.select_all")}
          </button>
          {sel.length > 0 && (
            <button type="button" className="btn btn-ghost" onClick={() => setSel([])}>
              <Icon name="x" /> {t("share.clear")} <span className="mono">({num(sel.length)})</span>
            </button>
          )}
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="empty share-empty">
          <Icon name="film" size={28} />
          <p style={{ margin: 0 }}>{clips.length ? t("share.none_here") : t("share.no_clips")}</p>
        </div>
      ) : (
        <ul className="share-grid" aria-label={t("share.title")}>
          {shown.map((c) => (
            <Tile
              key={c.id}
              pid={id}
              c={c}
              selected={sel.includes(c.id)}
              onSelect={() => toggle(c.id)}
              playing={playing === c.id}
              onPlay={(on) => setPlaying((p) => (on ? c.id : p === c.id ? null : p))}
              pending={c.id in pending}
              onShare={() => share([c.id])}
              onManual={() => setManual({ cid: c.id, title: c.title, platform: targets.find((p) => plats[p].usable) ?? "youtube" })}
              onRetry={() => retry([c.id])}
              onUnschedule={() => unschedule([c.id])}
              busy={busy}
            />
          ))}
        </ul>
      )}

      <FreeSpacePanel board={board} onOpen={() => setFreeOpen(true)} />

      {confirm && (
        <ConfirmShare
          plan={confirm.plan}
          busy={busy}
          onClose={() => setConfirm(null)}
          onGo={(extra) => publish({ ...confirm.body, ...extra }, confirm.plan.count)}
          onManual={(cid, title, p) => {
            setConfirm(null);
            setManual({ cid, title, platform: p });
          }}
        />
      )}
      {flow && (
        <ShareFlow
          pid={id}
          board={board}
          clipIds={flow}
          onClose={() => setFlow(null)}
          onStarted={() => {
            setFlow(null);
            setSel([]);
            shareChanged();
            load();
          }}
        />
      )}
      {manual && (
        <ManualUpload
          pid={id}
          cid={manual.cid}
          title={manual.title}
          platform={manual.platform}
          onClose={() => {
            setManual(null);
            load();
          }}
        />
      )}
      {connect && (
        <ConnectDialog
          p={connect}
          onClose={() => {
            setConnect(null);
            accountsChanged();
            load();
          }}
        />
      )}
      {freeOpen && <FreeSpaceDialog pid={id} onClose={() => setFreeOpen(false)} onDone={load} />}
    </div>
  );
}

function initialTargets(b: ShareBoard): Target[] {
  const remembered = b.targets.filter((p) => b.platforms[p].usable);
  if (remembered.length) return remembered;
  return ORDER.filter((p) => b.platforms[p].usable).slice(0, 1);
}

// ---------------------------------------------------------------- the video language

function LanguagePick({ pid, value, onChanged }: { pid: string; value: string; onChanged: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <label className="share-lang">
      <span className="field-label">{t("share.video_language")}</span>
      <select
        className="select"
        value={value}
        disabled={busy}
        onChange={(e) => {
          const code = e.target.value;
          setBusy(true);
          shareApi
            .setLanguage(pid, code)
            .then(() => {
              toast({ kind: "ok", text: t("share.language_set", { lang: UI_LANGUAGES.find((l) => l.code === code)?.name ?? code }) });
              onChanged();
            })
            .catch((er) => toast({ kind: "err", text: er.message, hint: er.hint }))
            .finally(() => setBusy(false));
        }}
      >
        {UI_LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.name}
          </option>
        ))}
      </select>
    </label>
  );
}

// ---------------------------------------------------------------- the choice before sharing

function ConfirmShare({
  plan,
  busy,
  onClose,
  onGo,
  onManual,
}: {
  plan: SharePlan;
  busy: boolean;
  onClose: () => void;
  onGo: (extra: Partial<ShareBody>) => void;
  onManual: (cid: string, title: string, p: Target) => void;
}) {
  const { t, num, lang } = useI18n();
  const [how, setHow] = useState<Overflow>("manual");
  const [day, setDay] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  });
  const [consent, setConsent] = useState(false);
  const going = plan.rows.filter((r) => r.platforms.length);
  const skipped = plan.rows.filter((r) => !r.platforms.length);
  const probs = going.filter((r) => r.problems.length);
  const reset = new Date(plan.limit.resets_at).toLocaleTimeString(`${lang}-u-nu-latn`, { hour: "2-digit", minute: "2-digit" });
  const minDay = (() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10);
  })();
  const blocked = probs.length > 0 || (plan.needs_consent && !consent);
  return (
    <Modal
      title={t("share.confirm_title", { n: num(plan.count) })}
      onClose={onClose}
      wide
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
            {t("common.cancel")}
          </button>
          <span style={{ flex: 1 }} />
          <button
            type="button"
            className="btn btn-primary btn-lg"
            disabled={busy || blocked}
            onClick={() =>
              onGo({
                consent,
                ...(plan.over > 0 ? { overflow: how, ...(how === "date" ? { overflow_date: day } : {}) } : {}),
              })
            }
          >
            {busy ? <span className="spinner" /> : <Icon name="upload" />} {t("share.share_now_n", { n: num(plan.count) })}
          </button>
        </>
      }
    >
      {plan.over > 0 && (
        <fieldset className="share-over">
          <legend>
            <Icon name="alert" /> {t("share.over_title", { fit: num(plan.uses_today), over: num(plan.over) })}
          </legend>
          <p className="muted" style={{ marginTop: 0 }}>
            {t("share.over_body", { n: num(plan.limit.limit) })}
          </p>
          <label className="share-radio">
            <input type="radio" name="over" checked={how === "manual"} onChange={() => setHow("manual")} />
            <span>
              <b>{t("share.over_manual")}</b>
              <span className="field-hint">{t("share.over_manual_hint")}</span>
            </span>
          </label>
          <label className="share-radio">
            <input type="radio" name="over" checked={how === "tomorrow"} onChange={() => setHow("tomorrow")} />
            <span>
              <b>{t("share.over_tomorrow")}</b>
              <span className="field-hint">{t("share.over_tomorrow_hint", { time: reset })}</span>
            </span>
          </label>
          <label className="share-radio">
            <input type="radio" name="over" checked={how === "date"} onChange={() => setHow("date")} />
            <span>
              <b>{t("share.over_date")}</b>
              <input
                className="input share-date"
                type="date"
                min={minDay}
                value={day}
                onChange={(e) => {
                  setDay(e.target.value);
                  setHow("date");
                }}
                aria-label={t("share.over_date")}
              />
            </span>
          </label>
        </fieldset>
      )}
      {going.some((r) => r.warnings?.length) && (
        <div className="notice notice-warn" role="note">
          <Icon name="alert" />
          <div>
            <div className="notice-title">{t("share.ig_warn_title")}</div>
            <div className="muted">{t("share.ig_warn_body", { h: num(plan.ig_gap_hours) })}</div>
          </div>
        </div>
      )}
      {skipped.length > 0 && (
        <div className="notice">
          <Icon name="check" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="notice-title">{t("share.sum_skipped", { n: skipped.length })}</div>
            <ul className="share-sum-skipped">
              {skipped.map((r) => (
                <li key={r.clip_id} dir="auto">
                  {r.title ?? r.clip_id}:{" "}
                  {r.skipped === "already"
                    ? t("share.skip_already", { where: r.already.map((a) => TARGET_NAME[a.platform]).join(", ") })
                    : r.skipped === "cant" && r.dropped?.length
                      ? r.dropped.map((x) => problemText(x, t)).join(" ")
                      : t("share.skip_no_platform")}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {probs.length > 0 && (
        <div className="notice notice-danger" role="alert">
          <Icon name="alert" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="notice-title">{t("share.sum_problems", { n: probs.length })}</div>
            <ul className="share-sum-skipped">
              {probs.map((r) => (
                <li key={r.clip_id} dir="auto">
                  {r.title}: {r.problems.map((x) => problemText(x, t)).join(" ")}{" "}
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => onManual(r.clip_id, r.title ?? r.clip_id, (r.platforms[0]?.platform ?? "youtube") as Target)}
                  >
                    {t("share.manual")}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {plan.needs_consent && (
        <label className="share-consent">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span>{t("share.tt_consent")}</span>
        </label>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- free up space

function FreeSpacePanel({ board, onOpen }: { board: ShareBoard; onOpen: () => void }) {
  const { t, num } = useI18n();
  const s = board.space;
  if (s.bytes <= 0 && !s.freed_at) return null;
  if (s.bytes <= 0)
    return (
      <p className="muted share-freed">
        <Icon name="check" size={14} /> {t("space.freed_note", { size: gb(s.freed_bytes ?? 0, num) })}
      </p>
    );
  return (
    <section className={`share-space${s.all_shared ? " is-ready" : ""}`} aria-label={t("space.title")}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h2 className="share-space-title">{s.all_shared ? t("space.all_shared") : t("space.title")}</h2>
        <p className="muted" style={{ margin: 0 }}>
          {t("space.body", { size: gb(s.bytes, num) })}
        </p>
      </div>
      <button type="button" className={`btn${s.all_shared ? " btn-primary" : ""}`} onClick={onOpen}>
        <Icon name="trash" /> {t("space.button", { size: gb(s.bytes, num) })}
      </button>
    </section>
  );
}

function FreeSpaceDialog({ pid, onClose, onDone }: { pid: string; onClose: () => void; onDone: () => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const meta = useMeta();
  const [s, setS] = useState<ShareBoard["space"] | null>(null);
  const [orig, setOrig] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    shareApi.space(pid).then(setS).catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  }, [pid, toast]);
  const total = s ? s.bytes + (orig && s.original ? s.original.bytes : 0) : 0;
  const go = () => {
    setBusy(true);
    shareApi
      .freeSpace(pid, orig)
      .then((r) => {
        toast({ kind: "ok", text: t("space.done", { size: gb(r.freed, num) }) });
        onDone();
        onClose();
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }))
      .finally(() => setBusy(false));
  };
  return (
    <Modal
      title={t("space.confirm_title")}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={busy}>
            {t("common.cancel")}
          </button>
          <span style={{ flex: 1 }} />
          <button type="button" className="btn btn-danger" onClick={go} disabled={!s || busy || s.waiting.length > 0 || total <= 0}>
            {busy ? <span className="spinner" /> : <Icon name="trash" />} {t("space.confirm", { size: gb(total, num) })}
          </button>
        </>
      }
    >
      {!s ? (
        <span className="spinner" />
      ) : (
        <>
          <p style={{ marginTop: 0 }}>{t("space.confirm_body", { size: gb(total, num) })}</p>
          <ul className="space-list">
            {s.source_bytes > 0 && <li>{t("space.part_source", { size: gb(s.source_bytes, num) })}</li>}
            {s.render_bytes > 0 && <li>{t("space.part_render", { size: gb(s.render_bytes, num) })}</li>}
          </ul>
          {s.original && meta?.is_local && (
            <label className="share-consent">
              <input type="checkbox" checked={orig} onChange={(e) => setOrig(e.target.checked)} />
              <span>
                {t("space.original", { size: gb(s.original.bytes, num) })}
                <span className="field-hint mono" style={{ display: "block", wordBreak: "break-all" }}>
                  {s.original.path}
                </span>
              </span>
            </label>
          )}
          <p className="field-hint">{t("space.keeps")}</p>
          {!s.all_shared && <p className="field-hint warn-text">{t("space.not_all", { n: num(s.clips - s.shared) })}</p>}
          {s.waiting.length > 0 && (
            <div className="notice notice-warn" role="alert">
              <Icon name="alert" />
              <div>{t("space.waiting", { n: num(s.waiting.length) })}</div>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- one card

const KIND_ICON: Record<ShareKind, string> = {
  not_shared: "upload",
  scheduled: "calendar",
  working: "refresh",
  shared: "check",
  failed: "alert",
};

function Tile({
  pid,
  c,
  selected,
  onSelect,
  playing,
  onPlay,
  pending,
  onShare,
  onManual,
  onRetry,
  onUnschedule,
  busy,
}: {
  pid: string;
  c: ShareCard;
  selected: boolean;
  onSelect: () => void;
  playing: boolean;
  onPlay: (on: boolean) => void;
  pending: boolean;
  onShare: () => void;
  onManual: () => void;
  onRetry: () => void;
  onUnschedule: () => void;
  busy: boolean;
}) {
  const { t, lang, num } = useI18n();
  const vid = useRef<HTMLVideoElement>(null);
  const hover = useRef<number | null>(null);
  const [sound, setSound] = useState(false);
  const s = c.status;
  const kind: ShareKind = pending ? "not_shared" : s.kind;
  const shared = isShared(c);
  const hasVideo = c.video.kind !== "none";
  const src =
    c.video.kind === "clip"
      ? urls.clip(pid, c.id, c.video.stamp)
      : `${urls.source(pid)}#t=${c.start.toFixed(2)},${c.end.toFixed(2)}`;
  const titleId = `sh-t-${c.id}`;

  useEffect(() => {
    const v = vid.current;
    if (!v) return;
    if (playing) {
      v.muted = !sound;
      if (c.video.kind === "source" && (v.currentTime < c.start || v.currentTime > c.end)) v.currentTime = c.start;
      v.play().catch(() => {});
    } else {
      v.pause();
    }
  }, [playing, sound, c.start, c.end, c.video.kind]);

  const onTime = () => {
    const v = vid.current;
    if (v && c.video.kind === "source" && v.currentTime >= c.end) v.currentTime = c.start; // loop the clip only
  };
  const enter = () => {
    if (!hasVideo || window.matchMedia("(hover: none)").matches) return;
    hover.current = window.setTimeout(() => onPlay(true), 350);
  };
  const leave = () => {
    if (hover.current) window.clearTimeout(hover.current);
    if (!sound) onPlay(false);
  };

  let label: string;
  if (kind === "shared") label = t("share.kind_shared");
  else if (kind === "scheduled")
    label = s.next_at
      ? t("share.kind_scheduled_at", { when: whenText(s.next_at, lang) })
      : s.planned.some((x) => x.by_hand)
        ? t("share.kind_by_hand")
        : t("share.kind_scheduled");
  else if (kind === "working") label = t("share.kind_working");
  else if (kind === "failed") label = t("share.kind_failed");
  else label = t("share.kind_not_shared");

  return (
    <li
      className={`sh-card kind-${kind}${selected ? " is-selected" : ""}${shared ? " is-shared" : ""}`}
      aria-labelledby={titleId}
    >
      <div className="sh-media" onMouseEnter={enter} onMouseLeave={leave}>
        {playing && hasVideo ? (
          <video
            ref={vid}
            src={src}
            className="sh-video"
            playsInline
            loop={c.video.kind === "clip"}
            muted={!sound}
            preload="metadata"
            onTimeUpdate={onTime}
            aria-label={c.title}
          />
        ) : hasVideo ? (
          <img className="sh-thumb" src={urls.frame(pid, c.peak, 640)} alt="" loading="lazy" decoding="async" />
        ) : (
          <div className="sh-thumb sh-nofile">
            <Icon name="film" size={26} />
            <span>{t("space.files_freed")}</span>
          </div>
        )}
        <label className="sh-check">
          <input type="checkbox" checked={selected} onChange={onSelect} aria-label={t("share.select_clip", { title: c.title })} />
          <span aria-hidden="true" />
        </label>
        {c.viral_score != null && (
          <span className="sh-score mono" title={t("share.score")}>
            <Icon name="zap" size={12} />
            {num(Math.round(c.viral_score))}
          </span>
        )}
        {hasVideo && (
          <button
            type="button"
            className="sh-play"
            onClick={() => {
              if (playing && sound) {
                setSound(false);
                onPlay(false);
              } else {
                setSound(true);
                onPlay(true);
              }
            }}
            aria-label={playing && sound ? t("share.pause") : t("share.play", { title: c.title })}
            aria-pressed={playing && sound}
          >
            <Icon name={playing && sound ? "pause" : "play"} size={22} />
          </button>
        )}
        <span className="sh-dur mono">{fmtTime(c.duration)}</span>
      </div>

      <div className="sh-body">
        <h2 className="sh-title" id={titleId} dir="auto">
          {c.title}
        </h2>
        <div className={`sh-badge badge-${kind}`}>
          <Icon name={KIND_ICON[kind]} size={13} />
          <span>{label}</span>
          {kind === "working" && s.progress != null && <span className="mono">{num(Math.round(s.progress * 100))}%</span>}
        </div>
        {(s.shared.length > 0 || s.planned.length > 0 || s.failed.length > 0 || s.busy.length > 0) && !pending && (
          <ul className="sh-plats" aria-label={t("share.where_now")}>
            {ORDER.map((p) => {
              const out = s.shared.find((x) => x.platform === p);
              const plan = s.planned.find((x) => x.platform === p);
              const bad = s.failed.find((x) => x.platform === p);
              const busyP = s.busy.includes(p);
              if (!out && !plan && !bad && !busyP) return null;
              const what = out
                ? t("share.p_out")
                : bad
                  ? t("share.p_failed")
                  : busyP
                    ? t("share.p_busy")
                    : plan?.at
                      ? whenText(plan.at, lang)
                      : t("share.p_by_hand");
              return (
                <li key={p} className={out ? "is-out" : bad ? "is-bad" : ""}>
                  <PlatformIcon p={p} size={15} />
                  {out?.url ? (
                    <a href={out.url} target="_blank" rel="noreferrer" title={t("share.open_post", { name: TARGET_NAME[p] })}>
                      {TARGET_NAME[p]} <Icon name="link" size={11} />
                    </a>
                  ) : (
                    <span>{TARGET_NAME[p]}</span>
                  )}
                  <span className="muted">{what}</span>
                </li>
              );
            })}
          </ul>
        )}
        {s.private.map((x) => (
          <div key={`pv-${x.platform}`} className="sh-private" role="note">
            <Icon name="lock" size={13} />
            <span>{t("share.private_note")}</span>
            {x.studio_url && (
              <a className="btn btn-sm" href={x.studio_url} target="_blank" rel="noreferrer">
                {t("notice.open_studio")}
              </a>
            )}
          </div>
        ))}
        {!pending &&
          s.waits.map((w) => (
            <p key={`w-${w.platform}`} className="sh-wait" dir="auto">
              <Icon name="clock" size={13} /> <b>{TARGET_NAME[w.platform]}:</b> {w.message}
              {w.hint && <span className="muted"> {w.hint}</span>}
            </p>
          ))}
        {kind === "failed" &&
          s.failed.map((f) => (
            <p key={`f-${f.platform}`} className="sh-error" dir="auto">
              <b>{TARGET_NAME[f.platform]}:</b> {f.message}
              {f.hint && <span className="muted"> {f.hint}</span>}
            </p>
          ))}
        {kind === "working" && <ProgressBar value={s.progress} label={label} />}
        <div className="sh-actions">
          {kind === "failed" && (
            <button type="button" className="btn btn-primary" onClick={onRetry}>
              <Icon name="refresh" /> {t("share.retry")}
            </button>
          )}
          {kind === "scheduled" && (
            <button type="button" className="btn" onClick={onUnschedule}>
              <Icon name="x" /> {t("share.unschedule")}
            </button>
          )}
          {kind !== "working" && kind !== "failed" && hasVideo && (
            <button
              type="button"
              className={`btn${kind === "not_shared" ? " btn-primary" : ""}`}
              onClick={onShare}
              disabled={busy}
              aria-describedby={titleId}
            >
              <Icon name="upload" /> {shared || kind === "scheduled" ? t("share.share_more") : t("share.share")}
            </button>
          )}
          {hasVideo && (
            <button type="button" className="btn btn-ghost" onClick={onManual} aria-describedby={titleId}>
              <Icon name="download" /> {t("share.manual")}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------- the batch progress panel

function BatchPanel({
  pid,
  batch,
  clips,
  onChanged,
  onUnschedule,
}: {
  pid: string;
  batch: Batch;
  clips: ShareCard[];
  onChanged: () => void;
  onUnschedule: (cids: string[]) => void;
}) {
  const { t, lang, num } = useI18n();
  const [open, setOpen] = useState(true);
  const by = new Map(clips.map((c) => [c.id, c]));
  const rows = batch.rows;
  const done = rows.filter((r) => r.state === "done" || r.state === "failed").length;
  const running = batch.state === "running";
  const cancelable = rows.filter((r) => {
    const k = by.get(r.clip_id)?.status.kind;
    return k === "scheduled" || k === "working";
  });
  return (
    <section className={`share-batch${running ? " is-running" : ""}`} aria-label={t("share.batch_title")}>
      <div className="share-batch-head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <h2 className="share-batch-title">
            {running ? t("share.batch_running") : batch.state === "stopped" ? t("share.batch_stopped") : t("share.batch_done")}
          </h2>
          <span className="muted mono">{t("share.batch_count", { done: num(done), n: num(rows.length) })}</span>
        </div>
        {cancelable.length > 0 && (
          <button type="button" className="btn" onClick={() => onUnschedule(cancelable.map((r) => r.clip_id))}>
            <Icon name="x" /> {t("share.batch_cancel")}
          </button>
        )}
        <button type="button" className="btn btn-ghost" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          <Icon name={open ? "chevron-up" : "chevron-down"} /> {open ? t("share.hide") : t("share.show")}
        </button>
        {!running && (
          <button
            type="button"
            className="btn btn-ghost icon-btn"
            aria-label={t("common.close")}
            onClick={() => shareApi.dismiss(pid).then(onChanged).catch(() => {})}
          >
            <Icon name="x" />
          </button>
        )}
      </div>
      <ProgressBar value={rows.length ? done / rows.length : null} label={t("share.batch_title")} />
      {open && (
        <ol className="share-batch-rows">
          {rows.map((r) => {
            const card = by.get(r.clip_id);
            const posts = card?.posts;
            return (
              <li key={r.clip_id} className={`br-${r.state}`}>
                <span className="br-state" aria-hidden="true">
                  {r.state === "done" ? (
                    <Icon name="check" size={14} />
                  ) : r.state === "failed" ? (
                    <Icon name="alert" size={14} />
                  ) : r.state === "starting" ? (
                    <span className="spinner" style={{ width: 12, height: 12 }} />
                  ) : (
                    <Icon name="clock" size={14} />
                  )}
                </span>
                <span className="br-title" dir="auto">
                  {r.title}
                </span>
                <span className="br-plats">
                  {r.platforms.map((p) => {
                    const st = posts?.[p];
                    const status = st?.status ?? "idle";
                    const txt =
                      status === "published"
                        ? t("share.p_out")
                        : status === "failed"
                          ? t("share.p_failed")
                          : ["preparing", "uploading", "processing"].includes(status)
                            ? t("share.p_busy")
                            : status === "ready"
                              ? t("share.p_by_hand")
                              : st?.publish_at
                                ? whenText(st.publish_at, lang)
                                : r.state === "queued"
                                  ? t("share.p_waiting")
                                  : r.when === "now"
                                    ? t("share.now")
                                    : whenText(r.when, lang);
                    return (
                      <span key={p} className={`br-plat st-${status}`}>
                        <PlatformIcon p={p} size={14} />
                        <span className="visually-hidden">{TARGET_NAME[p]}: </span>
                        {txt}
                      </span>
                    );
                  })}
                </span>
                {r.state === "failed" && r.error?.message && (
                  <span className="br-error" dir="auto">
                    {r.error.message}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

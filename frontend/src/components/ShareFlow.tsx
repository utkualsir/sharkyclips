// 1.2.66 / 1.2.68 Pro "Review & edit": 1 where (platform switches for all picked clips),
// optional "Edit per clip" (texts + platforms of each clip), 2 the summary (what goes where, now;
// a choice for what doesn't fit in today's YouTube uploads) -> Publish. The server makes the plan.
import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api";
import { useI18n } from "../i18n";
import { publishApi, TARGET_NAME, type PublishView, type Target } from "../multipost";
import { shareApi, whenText, type Overflow, type PlanRow, type ShareBoard, type SharePlan } from "../share";
import { useToast } from "../toast";
import { ConnectDialog, accountsChanged } from "./Accounts";
import { Icon } from "./Icons";
import { PlatformIcon } from "./PlatformIcons";
import { Modal } from "./ui";
import { problemText } from "./PublishAll";

const ORDER: Target[] = ["youtube", "reels", "tiktok"];
type Step = "where" | "edit" | "summary";

export function ShareFlow({
  pid,
  board,
  clipIds,
  onClose,
  onStarted,
}: {
  pid: string;
  board: ShareBoard;
  clipIds: string[];
  onClose: () => void;
  onStarted: () => void;
}) {
  const { t, num } = useI18n();
  const toast = useToast();
  const plats = board.platforms;
  const usable = ORDER.filter((p) => plats[p].usable);
  const [clips, setClips] = useState<string[]>(clipIds);
  const [step, setStep] = useState<Step>("where");
  const [targets, setTargets] = useState<Target[]>(() => {
    const remembered = board.targets.filter((p) => plats[p].usable);
    return remembered.length ? remembered : usable.slice(0, 1);
  });
  const [per, setPer] = useState<Record<string, Target[]>>({});
  const [plan, setPlan] = useState<SharePlan | null>(null);
  const [planErr, setPlanErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [consent, setConsent] = useState(false);
  const [overflow, setOverflow] = useState<Overflow>("manual");
  const [connect, setConnect] = useState<Target | null>(null);
  const cards = useMemo(() => board.clips.filter((c) => clips.includes(c.id)), [board.clips, clips]);
  const dupes = cards.filter((c) => c.status.kind !== "not_shared" && c.status.kind !== "failed");

  const body = () => ({
    clips,
    platforms: targets,
    per_clip: Object.fromEntries(Object.entries(per).filter(([c]) => clips.includes(c)).map(([c, p]) => [c, { platforms: p }])),
    consent,
    ...(plan && plan.over > 0 ? { overflow } : {}),
  });

  useEffect(() => {
    if (step !== "summary") return;
    setPlan(null);
    setPlanErr(null);
    shareApi
      .plan(pid, body())
      .then(setPlan)
      .catch((e) => setPlanErr(e instanceof ApiError ? e.message : String(e)));
  }, [step]); // eslint-disable-line react-hooks/exhaustive-deps

  const publish = () => {
    setBusy(true);
    shareApi
      .publish(pid, body())
      .then((r) => {
        toast({ kind: "ok", text: t("share.started_now", { n: num(r.plan.count) }), hint: t("share.started_hint") });
        onStarted();
      })
      .catch((e) => {
        toast({ kind: "err", text: e.message, hint: e.hint });
        if (e instanceof ApiError && e.code === "problems") setStep("edit");
      })
      .finally(() => setBusy(false));
  };

  const toggle = (p: Target) => setTargets((ts) => (ts.includes(p) ? ts.filter((x) => x !== p) : ORDER.filter((x) => x === p || ts.includes(x))));

  const title =
    step === "where" ? t("share.step_where") : step === "edit" ? t("share.step_edit") : t("share.step_summary");

  const footer =
    step === "where" ? (
      <>
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          {t("common.cancel")}
        </button>
        <span style={{ flex: 1 }} />
        <button type="button" className="btn" onClick={() => setStep("edit")} disabled={!targets.length}>
          <Icon name="list" /> {t("share.edit_per_clip")}
        </button>
        <button type="button" className="btn btn-primary btn-lg" onClick={() => setStep("summary")} disabled={!targets.length || !clips.length}>
          {t("share.next")} <Icon name="chevron-right" className="icon flip-rtl" />
        </button>
      </>
    ) : step === "edit" ? (
      <>
        <button type="button" className="btn btn-ghost" onClick={() => setStep("where")}>
          <Icon name="chevron-left" className="icon flip-rtl" /> {t("common.back")}
        </button>
        <span style={{ flex: 1 }} />
        <button type="button" className="btn btn-primary btn-lg" onClick={() => setStep("summary")} disabled={!clips.length}>
          {t("share.next")} <Icon name="chevron-right" className="icon flip-rtl" />
        </button>
      </>
    ) : (
      <>
        <button type="button" className="btn btn-ghost" onClick={() => setStep("where")} disabled={busy}>
          <Icon name="chevron-left" className="icon flip-rtl" /> {t("common.back")}
        </button>
        <span style={{ flex: 1 }} />
        <button
          type="button"
          className="btn btn-primary btn-lg"
          onClick={publish}
          disabled={busy || !plan || plan.count === 0 || plan.problems > 0 || (plan.needs_consent && !consent)}
        >
          {busy ? <span className="spinner" /> : <Icon name="upload" />} {t("share.publish", { n: num(plan?.count ?? 0) })}
        </button>
      </>
    );

  return (
    <>
      <Modal title={title} onClose={onClose} footer={footer} wide>
        <ol className="share-steps" aria-label={t("share.steps")}>
          {(["where", "summary"] as Step[]).map((s, i) => (
            <li key={s} aria-current={step === s || (s === "where" && step === "edit") ? "step" : undefined}>
              <span className="mono">{num(i + 1)}</span> {s === "where" ? t("share.step_where_short") : t("share.step_summary_short")}
            </li>
          ))}
        </ol>

        {step === "where" && (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              {t("share.where_lede", { n: clips.length })}
            </p>
            {dupes.length > 0 && (
              <div className="notice notice-warn share-dupes" role="alert">
                <Icon name="alert" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="notice-title">{t("share.dupe_title", { n: dupes.length })}</div>
                  <div className="muted">{t("share.dupe_body")}</div>
                </div>
                {dupes.length < clips.length && (
                  <button type="button" className="btn" onClick={() => setClips((cs) => cs.filter((c) => !dupes.some((d) => d.id === c)))}>
                    {t("share.dupe_leave_out")}
                  </button>
                )}
              </div>
            )}
            <div className="share-plats" role="group" aria-label={t("mp.where")}>
              {ORDER.map((p) => {
                const pl = plats[p];
                const on = targets.includes(p);
                if (!pl.usable) {
                  return (
                    <div key={p} className="share-plat is-off">
                      <PlatformIcon p={p} size={28} />
                      <span className="share-plat-name">{TARGET_NAME[p]}</span>
                      <span className="muted share-plat-mode">{t("share.not_connected")}</span>
                      <button type="button" className="btn btn-sm" onClick={() => setConnect(p)}>
                        {t("share.connect")}
                      </button>
                    </div>
                  );
                }
                return (
                  <button
                    key={p}
                    type="button"
                    className={`share-plat${on ? " is-on" : ""}`}
                    aria-pressed={on}
                    onClick={() => toggle(p)}
                  >
                    <PlatformIcon p={p} size={28} />
                    <span className="share-plat-name">{TARGET_NAME[p]}</span>
                    <span className="muted share-plat-mode">
                      {pl.manual ? t("share.mode_manual") : pl.by_hand ? t("share.mode_by_hand") : t("share.mode_auto")}
                    </span>
                    <span className="share-plat-check" aria-hidden="true">
                      {on && <Icon name="check" size={16} />}
                    </span>
                  </button>
                );
              })}
            </div>
            {targets.includes("reels") && (
              <p className="field-hint">{t("share.ig_pace_hint", { h: num(board.ig_gap_hours) })}</p>
            )}
          </>
        )}

        {step === "edit" && (
          <ul className="share-edit">
            {cards.map((c) => (
              <EditRow
                key={c.id}
                pid={pid}
                cid={c.id}
                title={c.title}
                usable={usable}
                value={per[c.id] ?? targets}
                onChange={(v) => setPer((m) => ({ ...m, [c.id]: v }))}
                onRemove={() => setClips((cs) => cs.filter((x) => x !== c.id))}
              />
            ))}
          </ul>
        )}

        {step === "summary" && (
          <Summary
            plan={plan}
            err={planErr}
            consent={consent}
            onConsent={setConsent}
            onEdit={() => setStep("edit")}
            overflow={overflow}
            onOverflow={setOverflow}
          />
        )}
      </Modal>
      {connect && (
        <ConnectDialog
          p={connect}
          onClose={() => {
            setConnect(null);
            accountsChanged();
          }}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------- edit per clip

function EditRow({
  pid,
  cid,
  title,
  usable,
  value,
  onChange,
  onRemove,
}: {
  pid: string;
  cid: string;
  title: string;
  usable: Target[];
  value: Target[];
  onChange: (v: Target[]) => void;
  onRemove: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<PublishView | null>(null);
  const [yt, setYt] = useState({ title: "", description: "", hashtags: "" });
  const [cap, setCap] = useState<{ tiktok: string; reels: string }>({ tiktok: "", reels: "" });
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!open || view) return;
    publishApi
      .view(pid, cid, value)
      .then((v) => {
        setView(v);
        setYt({ title: v.drafts.youtube.title, description: v.drafts.youtube.description, hashtags: v.drafts.youtube.hashtags.map((h) => `#${h}`).join(" ") });
        setCap({ tiktok: v.drafts.tiktok.caption, reels: v.drafts.reels.caption });
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = () =>
    publishApi
      .save(pid, cid, {
        drafts: {
          youtube: { title: yt.title, description: yt.description, hashtags: yt.hashtags.split(/\s+/).map((h) => h.replace(/^#+/, "")).filter(Boolean) },
          tiktok: { caption: cap.tiktok },
          reels: { caption: cap.reels },
        },
      })
      .then((v) => {
        setView(v);
        setSaved(true);
        window.setTimeout(() => setSaved(false), 2000);
      })
      .catch((e) => toast({ kind: "err", text: e.message, hint: e.hint }));
  const fid = `se-${cid}`;
  return (
    <li className="share-edit-row">
      <div className="share-edit-head">
        <span className="share-edit-title" dir="auto">
          {title}
        </span>
        <div className="share-edit-plats" role="group" aria-label={t("share.clip_platforms", { title })}>
          {ORDER.filter((p) => usable.includes(p)).map((p) => (
            <button
              key={p}
              type="button"
              className={`pf-toggle${value.includes(p) ? " is-on" : ""}`}
              aria-pressed={value.includes(p)}
              aria-label={TARGET_NAME[p]}
              title={TARGET_NAME[p]}
              onClick={() => onChange(value.includes(p) ? value.filter((x) => x !== p) : ORDER.filter((x) => x === p || value.includes(x)))}
            >
              <PlatformIcon p={p} size={18} />
            </button>
          ))}
        </div>
        <button type="button" className="btn btn-sm" aria-expanded={open} aria-controls={fid} onClick={() => setOpen((o) => !o)}>
          <Icon name="message" /> {t("share.texts")}
        </button>
        <button type="button" className="btn btn-sm btn-ghost icon-btn" onClick={onRemove} aria-label={t("share.leave_out", { title })}>
          <Icon name="x" />
        </button>
      </div>
      {open && (
        <div className="share-edit-body" id={fid}>
          {!view ? (
            <span className="spinner" />
          ) : (
            <>
              {value.includes("youtube") && (
                <fieldset className="share-fields">
                  <legend>
                    <PlatformIcon p="youtube" size={14} /> YouTube
                  </legend>
                  <label className="field">
                    <span className="field-label">{t("share.f_title")}</span>
                    <input
                      className="input"
                      dir="auto"
                      data-testid="share-title-input"
                      value={yt.title}
                      maxLength={view.limits.youtube.title}
                      onChange={(e) => setYt({ ...yt, title: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span className="field-label">{t("share.f_description")}</span>
                    <textarea className="input" dir="auto" rows={3} value={yt.description} onChange={(e) => setYt({ ...yt, description: e.target.value })} />
                  </label>
                  <label className="field">
                    <span className="field-label">{t("share.f_hashtags")}</span>
                    <input className="input" dir="auto" value={yt.hashtags} onChange={(e) => setYt({ ...yt, hashtags: e.target.value })} />
                  </label>
                </fieldset>
              )}
              {(["tiktok", "reels"] as const)
                .filter((p) => value.includes(p))
                .map((p) => (
                  <label key={p} className="field">
                    <span className="field-label">
                      <PlatformIcon p={p} size={14} /> {t("share.f_caption", { name: TARGET_NAME[p] })}
                    </span>
                    <textarea
                      className="input"
                      dir="auto"
                      rows={4}
                      data-testid="share-text-input"
                      value={cap[p]}
                      maxLength={view.limits[p].caption}
                      onChange={(e) => setCap({ ...cap, [p]: e.target.value })}
                    />
                  </label>
                ))}
              <div className="share-edit-save">
                <span className="field-hint" style={{ flex: 1 }}>
                  {t("share.template_hint")}
                </span>
                <button type="button" className="btn btn-primary" onClick={save}>
                  <Icon name="check" /> {saved ? t("common.saved") : t("common.save")}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------- the summary

function moveNote(m: string | null, t: ReturnType<typeof useI18n>["t"], h: number, num: (n: number) => string): string | null {
  if (m === "ig_pace") return t("share.moved_ig", { h: num(h) });
  if (m === "tiktok_cap") return t("share.moved_tiktok");
  return null;
}

function Summary({
  plan,
  err,
  consent,
  onConsent,
  onEdit,
  overflow,
  onOverflow,
}: {
  plan: SharePlan | null;
  err: string | null;
  consent: boolean;
  onConsent: (v: boolean) => void;
  onEdit: () => void;
  overflow: Overflow;
  onOverflow: (v: Overflow) => void;
}) {
  const { t, num } = useI18n();
  if (err)
    return (
      <div className="notice notice-danger" role="alert">
        <Icon name="alert" />
        <div>{err}</div>
      </div>
    );
  if (!plan)
    return (
      <div className="empty" style={{ padding: 24 }}>
        <span className="spinner" />
      </div>
    );
  const going = plan.rows.filter((r) => r.platforms.length);
  const skipped = plan.rows.filter((r) => !r.platforms.length);
  return (
    <div className="share-summary">
      <div className="share-sum-stats">
        <div>
          <b className="mono">{num(plan.count)}</b>
          <span>{t("share.sum_clips")}</span>
        </div>
        <div>
          <b className="mono">
            {num(plan.uses_today)}/{num(plan.limit.left)}
          </b>
          <span>{t("share.sum_today")}</span>
        </div>
        <div>
          <b className="mono">{num(plan.over)}</b>
          <span>{t("share.sum_over")}</span>
        </div>
      </div>
      {plan.over > 0 && (
        <div className="share-sum-note" role="group" aria-label={t("share.over_title", { fit: num(plan.uses_today), over: num(plan.over) })}>
          <Icon name="alert" size={15} /> {t("share.over_title", { fit: num(plan.uses_today), over: num(plan.over) })}{" "}
          <label className="share-radio-inline">
            <input type="radio" name="sf-over" checked={overflow === "manual"} onChange={() => onOverflow("manual")} />{" "}
            {t("share.over_manual")}
          </label>
          <label className="share-radio-inline">
            <input type="radio" name="sf-over" checked={overflow === "tomorrow"} onChange={() => onOverflow("tomorrow")} />{" "}
            {t("share.over_tomorrow")}
          </label>
        </div>
      )}
      <ol className="share-sum-rows">
        {going.map((r) => (
          <SumRow key={r.clip_id} r={r} gap={plan.ig_gap_hours} onEdit={onEdit} />
        ))}
      </ol>
      {skipped.length > 0 && (
        <div className="notice notice-warn">
          <Icon name="alert" />
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
      {plan.needs_consent && (
        <label className="share-consent">
          <input type="checkbox" checked={consent} onChange={(e) => onConsent(e.target.checked)} />
          <span>{t("share.tt_consent")}</span>
        </label>
      )}
      {plan.problems > 0 && (
        <div className="notice notice-danger" role="alert">
          <Icon name="alert" />
          <div style={{ flex: 1 }}>{t("share.sum_problems", { n: plan.problems })}</div>
          <button type="button" className="btn" onClick={onEdit}>
            {t("share.edit_per_clip")}
          </button>
        </div>
      )}
    </div>
  );
}

function SumRow({ r, gap, onEdit }: { r: PlanRow; gap: number; onEdit: () => void }) {
  const { t, lang, num } = useI18n();
  return (
    <li className={`share-sum-row${r.rolled ? " is-later" : ""}`}>
      <div className="share-sum-title" dir="auto">
        {r.title}
      </div>
      <ul className="share-sum-plats">
        {r.platforms.map((p) => {
          const note = moveNote(p.moved, t, gap, num);
          return (
            <li key={p.platform}>
              <PlatformIcon p={p.platform} size={16} />
              <span className="visually-hidden">{TARGET_NAME[p.platform]}: </span>
              <b className={p.when === "now" ? "is-now" : ""}>{p.when === "now" ? t("share.now") : whenText(p.when, lang)}</b>
              {(p.by_hand || p.manual) && <span className="chip chip-outline">{p.manual ? t("share.tag_reminder") : t("share.tag_by_hand")}</span>}
              {note && <span className="muted share-moved">{note}</span>}
            </li>
          );
        })}
      </ul>
      {r.already.length > 0 && (
        <div className="share-sum-already muted">
          <Icon name="check" size={12} /> {t("share.already_on", { where: r.already.map((a) => TARGET_NAME[a.platform]).join(", ") })}
        </div>
      )}
      {(r.warnings ?? []).map((w) => (
        <div key={`w-${w.code}`} className="share-sum-already muted">
          <Icon name="alert" size={12} /> {t("share.ig_warn_title")}
        </div>
      ))}
      {(r.dropped ?? []).map((x) => (
        <div key={`d-${x.platform}-${x.code}`} className="share-sum-already muted">
          <Icon name="x" size={12} /> {t("share.left_out_on", { name: x.platform === "all" ? "" : TARGET_NAME[x.platform] })}{" "}
          {problemText(x, t)}
        </div>
      ))}
      {r.problems.length > 0 && (
        <div className="share-sum-probs">
          <ul>
            {r.problems.map((x) => (
              <li key={`${x.platform}-${x.code}`}>{problemText(x, t)}</li>
            ))}
          </ul>
          <button type="button" className="btn btn-sm share-sum-fix" onClick={onEdit}>
            <Icon name="alert" /> {t("share.fix_n", { n: r.problems.length })}
          </button>
        </div>
      )}
    </li>
  );
}

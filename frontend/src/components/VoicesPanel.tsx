import { useEffect, useRef, useState } from "react";
import { api, type Job, type TrackLabel, type VoicesView } from "../api";
import { speakerLabel } from "../editing";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";

interface Props {
  projectId: string;
  jobs: Job[];
  llm: boolean;
  /** called when the voice pass finished (the plan / words change) */
  onDone: () => void;
  toast: (t: { kind: "ok" | "err"; text: string }) => void;
}

/** "Hear every speaker": audio tracks, the voice pass, speaker names, caption proofreading. */
export default function VoicesPanel({ projectId, jobs, llm, onDone, toast }: Props) {
  const { t, num } = useI18n();
  const [view, setView] = useState<VoicesView | null>(null);
  const [whole, setWhole] = useState(false);
  const [names, setNames] = useState<Record<string, string>>({});
  const job = jobs.find((j) => j.kind === "voices" && (j.status === "running" || j.status === "queued")) ?? null;
  const proofJob = jobs.find((j) => j.kind === "proofread" && (j.status === "running" || j.status === "queued")) ?? null;
  const busy = !!job;

  useEffect(() => {
    let cancelled = false;
    api
      .voices(projectId)
      .then((v) => {
        if (cancelled) return;
        setView(v);
        setNames(v.names ?? {});
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectId, busy]);
  // A voice pass or proofreading just finished: the clip's words / plan changed.
  const wasBusy = useRef(false);
  const proofing = !!proofJob;
  const wasProofing = useRef(false);
  useEffect(() => {
    if ((wasBusy.current && !busy) || (wasProofing.current && !proofing)) onDone();
    wasBusy.current = busy;
    wasProofing.current = proofing;
  }, [busy, proofing]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!view) return null;
  const multi = view.tracks.length > 1;
  const missing = Object.values(view.models.models).filter((m) => !m.ready).reduce((s, m) => s + m.size_mb, 0);
  const speakers = Object.entries(view.speakers ?? {});

  const run = () =>
    api
      .runVoices(projectId, whole)
      .then(() => toast({ kind: "ok", text: t("voices.started") }))
      .catch((e) => toast({ kind: "err", text: e.message }));

  const label = (pos: number, lab: TrackLabel) => {
    const labels = view.tracks.map((tr) => (tr.pos === pos ? lab : tr.label));
    api
      .setTrackLabels(projectId, labels)
      .then(setView)
      .catch((e) => toast({ kind: "err", text: e.message }));
  };

  const saveNames = () =>
    api
      .setSpeakerNames(projectId, names)
      .then((v) => {
        setView(v);
        onDone();
      })
      .catch((e) => toast({ kind: "err", text: e.message }));

  return (
    <div className="voices-panel">
      <div className="voices-head">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <Icon name="mic" size={14} />
          <b>{t("voices.title")}</b>
        </span>
        {view.done && !busy && (
          <span className="muted small">
            {view.mode === "tracks" ? t("voices.mode_tracks") : view.separated ? t("voices.mode_separated") : t("voices.mode_mix")}
          </span>
        )}
      </div>
      {multi && (
        <div className="voices-tracks">
          <span className="muted small">{view.labels_from === "remembered" ? t("voices.tracks_remembered") : t("voices.tracks_hint")}</span>
          {view.tracks.map((tr) => (
            <label key={tr.pos} className="voices-track">
              <span className="voices-track-name" title={tr.title}>
                {t("voices.track_n", { n: tr.pos + 1 })}
                {tr.title ? ` · ${tr.title}` : ""}
              </span>
              <select className="select select-sm" value={tr.label} onChange={(e) => label(tr.pos, e.target.value as TrackLabel)}>
                {view.labels.map((l) => (
                  <option key={l} value={l}>
                    {t(`voices.label.${l}`)}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      )}
      {busy ? (
        <div className="muted small" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="spinner" style={{ width: 12, height: 12 }} />
          {t(`stage.${job!.stage ?? "voices_separating"}`)}
          {job!.progress != null && ` · ${Math.round(job!.progress * 100)}%`}
        </div>
      ) : (
        <>
          {!view.done && <p className="muted small" style={{ margin: 0 }}>{t("voices.hint")}</p>}
          {view.done && speakers.length > 0 && (
            <div className="voices-speakers">
              {speakers.map(([id, s]) => (
                <label key={id} className="voices-speaker">
                  <span className={`spk-chip spk-${id}`}>{speakerLabel(id, {}, t)}</span>
                  <input
                    className="input input-sm"
                    value={names[id] ?? ""}
                    placeholder={speakerLabel(id, {}, t)}
                    maxLength={24}
                    onChange={(e) => setNames({ ...names, [id]: e.target.value })}
                    onBlur={() => (names[id] ?? "") !== (view.names?.[id] ?? "") && saveNames()}
                    aria-label={t("voices.name_for", { who: speakerLabel(id, {}, t) })}
                  />
                  <span className="muted small tc">{num(Math.round(s.seconds))} s</span>
                  {id !== "me" && (
                    <select
                      className="select select-sm voices-merge"
                      value=""
                      aria-label={t("voices.merge_into", { who: speakerLabel(id, view.names, t) })}
                      title={t("voices.merge_hint")}
                      onChange={(e) => {
                        const into = e.target.value;
                        if (!into) return;
                        api
                          .mergeSpeakers(projectId, id, into)
                          .then((v) => {
                            setView(v);
                            setNames(v.names ?? {});
                            onDone();
                          })
                          .catch((err) => toast({ kind: "err", text: err.message }));
                      }}
                    >
                      <option value="">{t("voices.same_as")}</option>
                      {speakers
                        .filter(([o]) => o !== id)
                        .map(([o]) => (
                          <option key={o} value={o}>
                            {speakerLabel(o, view.names, t)}
                          </option>
                        ))}
                    </select>
                  )}
                </label>
              ))}
            </div>
          )}
          {view.done && view.stale && <p className="small gold" style={{ margin: 0 }}>{t("voices.stale")}</p>}
          <div className="voices-actions">
            <button className="btn btn-sm" onClick={run}>
              <Icon name="mic" />
              {view.done ? t("voices.run_again") : t("voices.run")}
            </button>
            <label className="edit-check small">
              <input type="checkbox" checked={whole} onChange={(e) => setWhole(e.target.checked)} />
              {t("voices.whole")}
            </label>
            {llm && view.done && (
              <button
                className="btn btn-sm btn-ghost"
                disabled={!!proofJob}
                onClick={() =>
                  api
                    .proofread(projectId, true)
                    .then(() => toast({ kind: "ok", text: t("voices.proof_started") }))
                    .catch((e) => toast({ kind: "err", text: e.message }))
                }
                title={t("voices.proof_hint")}
              >
                {proofJob ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <Icon name="sparkles" />}
                {t("voices.proof")}
              </button>
            )}
          </div>
          {missing > 0 && <p className="muted small" style={{ margin: 0 }}>{t("voices.download", { mb: num(missing) })}</p>}
        </>
      )}
    </div>
  );
}

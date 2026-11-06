// 1.2.18 my-voice dubbing: the one-time voice setup (consent + own sample) and the per-clip switch.
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { dubApi, voiceApi, type ClipDub, type VoiceProfile } from "../extras";
import { useI18n } from "../i18n";
import { isActive, useJobs } from "../jobs";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { JobLine, Modal, Toggle } from "./ui";

const RECORD_SECONDS = 20;

/** Consent first (both boxes + name), then a recording or a file, only of the user's own voice. */
export function VoiceSetup({ onClose, onReady }: { onClose: () => void; onReady?: (p: VoiceProfile) => void }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const [p, setP] = useState<VoiceProfile | null>(null);
  const [name, setName] = useState("");
  const [own, setOwn] = useState(false);
  const [noOthers, setNoOthers] = useState(false);
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState<number | null>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const [v, setV] = useState(0);
  useEffect(() => {
    voiceApi.profile().then(setP).catch(() => {});
    return () => rec.current?.stream.getTracks().forEach((tr) => tr.stop());
  }, []);
  if (!p) return null;

  const done = (np: VoiceProfile) => {
    setP(np);
    setV((x) => x + 1);
    if (np.ready) onReady?.(np);
  };
  const consent = async () => {
    setBusy(true);
    try {
      done(await voiceApi.consent(name, own, noOthers));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const upload = async (blob: Blob, source: "recorded" | "file") => {
    setBusy(true);
    try {
      done(await voiceApi.sample(blob, source));
      toast({ kind: "ok", text: t("voice.sample_saved") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const record = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const r = new MediaRecorder(stream);
      const parts: Blob[] = [];
      r.ondataavailable = (e) => e.data.size && parts.push(e.data);
      r.onstop = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setLeft(null);
        upload(new Blob(parts, { type: r.mimeType || "audio/webm" }), "recorded");
      };
      rec.current = r;
      r.start();
      let s = RECORD_SECONDS;
      setLeft(s);
      const id = window.setInterval(() => {
        s -= 1;
        setLeft(s);
        if (s <= 0 || r.state !== "recording") {
          window.clearInterval(id);
          if (r.state === "recording") r.stop();
        }
      }, 1000);
    } catch {
      toast({ kind: "err", text: t("voice.mic_denied"), hint: t("voice.mic_hint") });
    }
  };

  return (
    <Modal
      title={t("voice.setup_title")}
      onClose={onClose}
      footer={
        <button className="btn" onClick={onClose}>
          {t("common.close")}
        </button>
      }
    >
      <p className="muted">{t("voice.intro")}</p>
      {!p.consent ? (
        <fieldset className="ez-field">
          <legend>{t("voice.consent_title")}</legend>
          <label className="check-line">
            <input type="checkbox" checked={own} onChange={(e) => setOwn(e.target.checked)} />
            <span>{t("voice.consent_own")}</span>
          </label>
          <label className="check-line">
            <input type="checkbox" checked={noOthers} onChange={(e) => setNoOthers(e.target.checked)} />
            <span>{t("voice.consent_others")}</span>
          </label>
          <label className="field">
            <span className="field-label">{t("voice.your_name")}</span>
            <input className="input" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} />
          </label>
          <div>
            <button className="btn btn-primary" disabled={busy || !own || !noOthers || !name.trim()} onClick={consent}>
              {t("voice.agree")}
            </button>
          </div>
        </fieldset>
      ) : (
        <fieldset className="ez-field">
          <legend>{t("voice.sample_title")}</legend>
          <p className="field-hint">{t("voice.read_this")}</p>
          <blockquote className="voice-script" dir="auto">
            {t("voice.script")}
          </blockquote>
          <div className="inline-row" style={{ flexWrap: "wrap" }}>
            {left != null ? (
              <button className="btn btn-primary" onClick={() => rec.current?.stop()}>
                <Icon name="stop" /> {t("voice.stop", { s: num(left) })}
              </button>
            ) : (
              <button className="btn btn-primary" disabled={busy} onClick={record}>
                <Icon name="mic" /> {t(p.sample ? "voice.record_again" : "voice.record")}
              </button>
            )}
            <button className="btn" disabled={busy || left != null} onClick={() => file.current?.click()}>
              <Icon name="file" /> {t("voice.pick_file")}
            </button>
            {busy && <span className="spinner" />}
          </div>
          <input
            ref={file}
            type="file"
            hidden
            accept="audio/*,video/*"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f, "file");
              e.target.value = "";
            }}
          />
          {p.sample && (
            <>
              <p className="field-hint">
                <Icon name="check" size={12} /> {t("voice.sample_ok", { s: num(p.sample_seconds ?? 0) })}
              </p>
              <audio controls src={`/api/voice/sample.wav?v=${v}`} style={{ width: "100%" }} aria-label={t("voice.sample_title")} />
            </>
          )}
          <p className="field-hint">{t("voice.local_only", { mb: num(p.model_mb) })}</p>
        </fieldset>
      )}
    </Modal>
  );
}

/** One switch per clip: "Speak English in my voice". Re-renders the clip when done. */
export function DubSwitch({ pid, cid, compact }: { pid: string; cid: string; compact?: boolean }) {
  const { t, num } = useI18n();
  const toast = useToast();
  const { jobs, finishedTick } = useJobs();
  const [d, setD] = useState<ClipDub | null>(null);
  const [setup, setSetup] = useState(false);
  const job = jobs.find((j) => j.kind === "dub" && j.project_id === pid && j.params?.clip_id === cid && isActive(j)) ?? null;
  useEffect(() => {
    dubApi.clip(pid, cid).then(setD).catch(() => {});
  }, [pid, cid, finishedTick]);
  if (!d) return null;
  const target = d.targets[0] ?? "en";
  const langName = t(`dub.lang.${target}`);
  const on = !!d.lang || !!job;
  const flip = async (v: boolean) => {
    if (v && !d.profile.ready) {
      setSetup(true);
      return;
    }
    try {
      setD(await dubApi.set(pid, cid, v ? target : ""));
    } catch (e: any) {
      if (e.code === "voice_setup") setSetup(true);
      else toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <div className={compact ? "ez-toggles" : "dub-box"}>
      <div className="toggle-line">
        <span>
          <b>{t("dub.switch", { lang: langName })}</b>
          <span className="muted ez-hint" style={{ display: "block" }}>
            {d.info ? t("dub.result", { n: num(d.info.dubbed), k: num(d.info.kept) }) : t("dub.hint")}
          </span>
        </span>
        <Toggle checked={on} onChange={flip} label={t("dub.switch", { lang: langName })} />
      </div>
      {job && <JobLine job={job} onCancel={() => api.cancelJob(job.id).catch(() => {})} />}
      {d.profile.ready && (
        <button type="button" className="link-btn field-hint" onClick={() => setSetup(true)}>
          <Icon name="mic" size={12} /> {t("voice.manage")}
        </button>
      )}
      {setup && (
        <VoiceSetup
          onClose={() => setSetup(false)}
          onReady={() => dubApi.clip(pid, cid).then(setD).catch(() => {})}
        />
      )}
    </div>
  );
}

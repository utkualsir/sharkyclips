import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { api, type ConnectFlow, type YoutubeStatus } from "../api";
import { useAppState } from "../appstate";
import { useI18n } from "../i18n";
import { useMeta } from "../meta";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { Modal } from "./ui";

// "Connect with Google" (1.2.8): one button, Google's page in the system browser, and the app
// updates by itself the moment Google sends the browser back (a one-shot listener on a random
// 127.0.0.1 port in the backend, see ytconnect.py). Used by Settings, the onboarding, the
// publish dialogs and the "signed out" banner.

const TIP_KEY = "sc-yt-warning-tip-seen";
const CONSOLE = "https://console.cloud.google.com";

function tipSeen(): boolean {
  try {
    return localStorage.getItem(TIP_KEY) === "1";
  } catch {
    return false;
  }
}

function setTipSeen() {
  try {
    localStorage.setItem(TIP_KEY, "1");
  } catch {
    /* private window: show it again next time */
  }
}

/** Google's "G" (multicolor, as Google's sign-in branding asks). */
function GoogleG({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

/** A channel picture that fails to load (offline) leaves no broken-image icon. */
export const hideImg = (e: { currentTarget: HTMLImageElement }) => {
  e.currentTarget.style.visibility = "hidden";
};

// ---------------------------------------------------------------- the connect flow

type Phase = "idle" | "tip" | "waiting";

/** The whole sign-in: optional warning tip, the browser, waiting, the outcome. */
export function useYoutubeConnect(
  yt: YoutubeStatus | null,
  onStatus: (s: YoutubeStatus) => void,
) {
  const { t } = useI18n();
  const toast = useToast();
  const { refresh: refreshApp } = useAppState();
  const [phase, setPhase] = useState<Phase>("idle");
  const [flow, setFlow] = useState<ConnectFlow | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [since, setSince] = useState(0);
  const flowId = useRef<string | null>(null);

  const open = async () => {
    try {
      const r = await api.youtubeConnect(true);
      flowId.current = r.id;
      setUrl(r.url);
      setFlow({
        id: r.id,
        status: "waiting",
        message: null,
        hint: null,
        reason: null,
        youtube: null,
      });
      setSince(Date.now());
      setPhase("waiting");
      if (!r.opened) window.open(r.url, "_blank", "noopener");
    } catch (e: any) {
      setPhase("idle");
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  const start = () => {
    const warn = yt?.mode === "shared" && yt.shared.verification !== "verified";
    if (warn && !tipSeen()) setPhase("tip");
    else open();
  };

  const cancel = async () => {
    const id = flowId.current;
    flowId.current = null;
    setPhase("idle");
    setFlow(null);
    if (id) api.youtubeConnectCancel(id).catch(() => {});
  };

  useEffect(() => {
    if (phase !== "waiting") return;
    let stop = false;
    const tick = async () => {
      const id = flowId.current;
      if (!id || stop) return;
      try {
        const f = await api.youtubeConnectState(id);
        if (stop || id !== flowId.current) return;
        if (f.status === "waiting") return;
        flowId.current = null;
        setFlow(f);
        setPhase("idle");
        if (f.youtube) onStatus(f.youtube);
        refreshApp();
        if (f.status === "ok" && f.youtube?.channel)
          toast({
            kind: "ok",
            text: t("ytc.connected_toast", { name: f.youtube.channel.title }),
          });
      } catch {
        /* server busy: next tick */
      }
    };
    const id = window.setInterval(tick, 700);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    phase,
    flow,
    url,
    since,
    start,
    open,
    cancel,
    closeTip: () => setPhase("idle"),
    clearFlow: () => setFlow(null),
  };
}

/** The big "Connect with Google" button and everything that follows it. */
export function ConnectYoutube({
  yt,
  onStatus,
  big = true,
  label,
  onAdvanced,
}: {
  yt: YoutubeStatus | null;
  onStatus: (s: YoutubeStatus) => void;
  big?: boolean;
  label?: string;
  /** "use your own Google project" (shown when the one-click connection isn't available) */
  onAdvanced?: () => void;
}) {
  const { t } = useI18n();
  const meta = useMeta();
  const c = useYoutubeConnect(yt, onStatus);
  if (meta && !meta.is_local)
    return <p className="muted">{t("yt.local_only")}</p>;
  if (yt && !yt.ready)
    return (
      <div className="notice">
        <Icon name="alert" />
        <span>
          {t("ytc.not_ready")}{" "}
          {onAdvanced && (
            <button className="link-btn" onClick={onAdvanced}>
              {t("ytc.adv_start")}
            </button>
          )}
        </span>
      </div>
    );
  return (
    <div className="ytc">
      {c.phase === "waiting" ? (
        <Waiting
          url={c.url}
          since={c.since}
          own={yt?.mode === "own"}
          onCancel={c.cancel}
        />
      ) : (
        <>
          <button
            className={`gbtn${big ? " gbtn-big" : ""}`}
            onClick={c.start}
            disabled={!yt}
          >
            <span className="gbtn-g">
              <GoogleG size={big ? 20 : 18} />
            </span>
            <span>{label ?? t("ytc.connect_google")}</span>
          </button>
          {big && <p className="ytc-sub muted">{t("ytc.ten_seconds")}</p>}
          <FlowResult
            flow={c.flow}
            onRetry={c.start}
            onDismiss={c.clearFlow}
            projectId={yt?.project_id ?? null}
          />
        </>
      )}
      {c.phase === "tip" && (
        <WarningTip
          onClose={c.closeTip}
          onGo={(remember) => {
            if (remember) setTipSeen();
            c.open();
          }}
        />
      )}
    </div>
  );
}

function Waiting({
  url,
  since,
  own,
  onCancel,
}: {
  url: string | null;
  since: number;
  own: boolean;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(
      () => setStuck(true),
      Math.max(0, 20_000 - (Date.now() - since)),
    );
    return () => window.clearTimeout(id);
  }, [since]);
  return (
    <div className="ytc-wait" role="status" aria-live="polite">
      <div className="ytc-wait-head">
        <span className="spinner" aria-hidden="true" />
        <div>
          <b>{t("ytc.waiting_title")}</b>
          <p className="muted">{t("ytc.waiting_body")}</p>
        </div>
      </div>
      <div className="ytc-wait-actions">
        {url && (
          <a className="btn btn-sm" href={url} target="_blank" rel="noreferrer">
            <Icon name="link" />
            {t("ytc.open_again")}
          </a>
        )}
        <button className="btn btn-sm btn-ghost" onClick={onCancel}>
          {t("common.cancel")}
        </button>
      </div>
      <details className="ytc-stuck" open={stuck}>
        <summary>{t("ytc.stuck_title")}</summary>
        <ul>
          <li>{t("ytc.stuck_account")}</li>
          <li>{t("ytc.stuck_warning")}</li>
          <li>{own ? t("ytc.stuck_own_blocked") : t("ytc.stuck_blocked")}</li>
        </ul>
      </details>
    </div>
  );
}

function FlowResult({
  flow,
  onRetry,
  onDismiss,
  projectId,
}: {
  flow: ConnectFlow | null;
  onRetry: () => void;
  onDismiss: () => void;
  projectId: string | null;
}) {
  const { t } = useI18n();
  if (
    !flow ||
    flow.status === "ok" ||
    flow.status === "waiting" ||
    flow.status === "no_channel" ||
    flow.status === "choose_channel"
  )
    return null;
  const api_off = flow.status === "api_disabled";
  const text =
    flow.status === "cancelled"
      ? t("ytc.cancelled")
      : flow.status === "expired"
        ? t("ytc.expired")
        : api_off
          ? t("ytc.api_disabled")
          : flow.message;
  return (
    <div
      className={`notice${flow.status === "cancelled" ? "" : " notice-warn"} ytc-result`}
      role="alert"
    >
      <Icon name="alert" />
      <span>
        {text}
        {flow.status === "error" && flow.hint && (
          <span className="muted"> {flow.hint}</span>
        )}{" "}
        {api_off && (
          <a
            href={`${CONSOLE}/apis/library/youtube.googleapis.com${projectId ? `?project=${encodeURIComponent(projectId)}` : ""}`}
            target="_blank"
            rel="noreferrer"
          >
            {t("ytc.api_enable")}
          </a>
        )}{" "}
        <button className="link-btn" onClick={onRetry}>
          {t("ytc.try_again")}
        </button>
      </span>
      <button
        className="btn btn-ghost icon-btn"
        onClick={onDismiss}
        aria-label={t("ytc.dismiss")}
      >
        <Icon name="x" size={14} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------- the warning-screen tip

function WarningTip({
  onClose,
  onGo,
}: {
  onClose: () => void;
  onGo: (remember: boolean) => void;
}) {
  const { t } = useI18n();
  const [remember, setRemember] = useState(false);
  // on <body>: a dialog inside an animated page / card would be clipped or covered
  return createPortal(
    <div className="ytc-modal-layer">
      <Modal
        top
        title={t("ytc.tip_title")}
        onClose={onClose}
        footer={
          <>
            <label className="ytc-check">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              <span>{t("ytc.tip_dont_show")}</span>
            </label>
            <span style={{ flex: 1 }} />
            <button className="btn btn-ghost" onClick={onClose}>
              {t("common.cancel")}
            </button>
            <button className="btn btn-primary" onClick={() => onGo(remember)}>
              <GoogleG size={16} />
              {t("ytc.tip_ok")}
            </button>
          </>
        }
      >
        <p style={{ marginTop: 0 }}>{t("ytc.tip_body")}</p>
        <WarningIllustration />
      </Modal>
    </div>,
    document.body,
  );
}

/** A drawing of Google's "unverified app" screen with the two clicks marked. */
function WarningIllustration() {
  const { t, dir } = useI18n();
  const rtl = dir === "rtl";
  const x = (v: number, w = 0) => (rtl ? 320 - v - w : v);
  const anchor = rtl ? "end" : "start";
  return (
    <figure className="ytc-ill">
      <svg viewBox="0 0 320 200" role="img" aria-label={t("ytc.ill_caption")}>
        <rect
          x="1"
          y="1"
          width="318"
          height="198"
          rx="12"
          className="ill-frame"
        />
        <rect x="1" y="1" width="318" height="22" rx="12" className="ill-bar" />
        <circle cx={x(14)} cy="12" r="3.5" className="ill-dot" />
        <circle cx={x(26)} cy="12" r="3.5" className="ill-dot" />
        <circle cx={x(38)} cy="12" r="3.5" className="ill-dot" />
        <g transform={`translate(${x(20, 22)} 36)`}>
          <path d="M11 1 21 19H1z" className="ill-warn" />
          <path d="M11 7v6M11 15.5v.5" className="ill-warn-mark" />
        </g>
        <text x={x(20)} y="76" textAnchor={anchor} className="ill-h">
          {t("ytc.ill_title")}
        </text>
        <rect
          x={x(20, 230)}
          y="86"
          width="230"
          height="6"
          rx="3"
          className="ill-line"
        />
        <rect
          x={x(20, 180)}
          y="98"
          width="180"
          height="6"
          rx="3"
          className="ill-line"
        />
        {/* 1: Advanced */}
        <text x={x(20)} y="128" textAnchor={anchor} className="ill-link">
          {t("ytc.ill_advanced")}
        </text>
        <rect
          x={x(12, 120)}
          y="113"
          width="120"
          height="22"
          rx="8"
          className="ill-ring"
        />
        <g transform={`translate(${x(138, 20)} 114)`}>
          <circle cx="10" cy="10" r="10" className="ill-num" />
          <text x="10" y="14.5" textAnchor="middle" className="ill-num-t">
            1
          </text>
        </g>
        <rect
          x={x(220, 82)}
          y="114"
          width="82"
          height="22"
          rx="11"
          className="ill-btn"
        />
        <text x={x(261)} y="129" textAnchor="middle" className="ill-btn-t">
          {t("ytc.ill_back")}
        </text>
        {/* 2: Go to SharkyClips */}
        <rect
          x={x(20, 150)}
          y="148"
          width="150"
          height="6"
          rx="3"
          className="ill-line"
        />
        <text x={x(20)} y="178" textAnchor={anchor} className="ill-link">
          {t("ytc.ill_goto")}
        </text>
        <rect
          x={x(12, 210)}
          y="163"
          width="210"
          height="22"
          rx="8"
          className="ill-ring"
        />
        <g transform={`translate(${x(228, 20)} 164)`}>
          <circle cx="10" cy="10" r="10" className="ill-num" />
          <text x="10" y="14.5" textAnchor="middle" className="ill-num-t">
            2
          </text>
        </g>
      </svg>
      <figcaption className="muted">{t("ytc.ill_caption")}</figcaption>
    </figure>
  );
}

// ---------------------------------------------------------------- after the sign-in

export function NoChannel({
  yt,
  onStatus,
}: {
  yt: YoutubeStatus;
  onStatus: (s: YoutubeStatus) => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const check = async () => {
    setBusy(true);
    try {
      const s = await api.youtubeRecheck();
      onStatus(s);
      if (s.no_channel)
        toast({ kind: "info", text: t("ytc.still_no_channel") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  return (
    <div className="notice notice-warn ytc-nochannel" role="status">
      <Icon name="alert" />
      <div>
        <b className="notice-title">{t("ytc.no_channel_title")}</b>
        <p className="muted" style={{ margin: "2px 0 8px" }}>
          {t("ytc.no_channel_body")}
        </p>
        <div className="ytc-row">
          <a
            className="btn btn-sm btn-primary"
            href={yt.create_channel_url}
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="plus" />
            {t("ytc.create_channel")}
          </a>
          <button className="btn btn-sm" onClick={check} disabled={busy}>
            {busy ? (
              <span className="spinner" style={{ width: 12, height: 12 }} />
            ) : (
              <Icon name="refresh" />
            )}
            {t("ytc.check_again")}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ChannelPicker({
  yt,
  onStatus,
}: {
  yt: YoutubeStatus;
  onStatus: (s: YoutubeStatus) => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  if (yt.channels.length < 2) return null;
  const pick = async (id: string) => {
    try {
      onStatus(await api.youtubeChannel(id));
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  return (
    <fieldset className="ytc-channels">
      <legend>{t("ytc.pick_channel")}</legend>
      {yt.channels.map((c) => (
        <label
          key={c.id}
          className={`ytc-channel${yt.channel?.id === c.id ? " on" : ""}`}
        >
          <input
            type="radio"
            name="yt-channel"
            checked={yt.channel?.id === c.id}
            onChange={() => pick(c.id)}
          />
          {c.thumbnail ? (
            <img
              src={c.thumbnail}
              alt=""
              referrerPolicy="no-referrer"
              onError={hideImg}
            />
          ) : (
            <span className="ytc-avatar-ph" aria-hidden="true" />
          )}
          <span>{c.title}</span>
        </label>
      ))}
      <p className="muted ytc-sub">{t("ytc.pick_channel_hint")}</p>
    </fieldset>
  );
}

/** The connected account with "Use another account" (Google's chooser again). */
export function YoutubeAccount({
  yt,
  onStatus,
  onDisconnect,
  meta,
}: {
  yt: YoutubeStatus;
  onStatus: (s: YoutubeStatus) => void;
  onDisconnect?: () => void;
  meta?: ReactNode;
}) {
  const { t } = useI18n();
  const c = useYoutubeConnect(yt, onStatus);
  return (
    <>
      <div className="yt-account">
        {yt.channel?.thumbnail ? (
          <img
            src={yt.channel.thumbnail}
            alt=""
            referrerPolicy="no-referrer"
            onError={hideImg}
          />
        ) : (
          <span className="ytc-avatar-ph" aria-hidden="true" />
        )}
        <div style={{ minWidth: 0 }}>
          <b className="ytc-name">{yt.channel?.title ?? t("yt.connected")}</b>
          {meta}
        </div>
        <span style={{ flex: 1 }} />
        <div className="ytc-row">
          <button
            className="btn btn-sm btn-ghost"
            onClick={c.start}
            disabled={c.phase === "waiting"}
          >
            <GoogleG size={14} />
            {t("ytc.switch_account")}
          </button>
          {onDisconnect && (
            <button className="btn btn-sm btn-ghost" onClick={onDisconnect}>
              {t("yt.disconnect")}
            </button>
          )}
        </div>
      </div>
      {c.phase === "waiting" && (
        <Waiting
          url={c.url}
          since={c.since}
          own={yt.mode === "own"}
          onCancel={c.cancel}
        />
      )}
      {c.phase === "tip" && (
        <WarningTip
          onClose={c.closeTip}
          onGo={(remember) => {
            if (remember) setTipSeen();
            c.open();
          }}
        />
      )}
      <FlowResult
        flow={c.flow}
        onRetry={c.start}
        onDismiss={c.clearFlow}
        projectId={yt.project_id}
      />
    </>
  );
}

/** "Connect YouTube to publish": shown in a publish dialog while YouTube isn't connected. */
export function ConnectPrompt({
  onConnected,
}: {
  onConnected: (s: YoutubeStatus) => void;
}) {
  const { t } = useI18n();
  const [yt, setYt] = useState<YoutubeStatus | null>(null);
  useEffect(() => {
    api
      .youtube()
      .then(setYt)
      .catch(() => {});
  }, []);
  const update = (s: YoutubeStatus) => {
    setYt(s);
    if (s.connected) onConnected(s);
  };
  return (
    <div className="ytc-prompt">
      <div className="ytc-prompt-text">
        <b>{t("ytc.prompt_title")}</b>
        <span className="muted">{t("ytc.prompt_body")}</span>
      </div>
      <ConnectYoutube
        yt={yt}
        onStatus={update}
        big={false}
        onAdvanced={() => (window.location.hash = "#/settings")}
      />
    </div>
  );
}

// ---------------------------------------------------------------- "signed out" banner

/** Google ended the sign-in (revoked / expired): one click on any screen reconnects. */
export function YoutubeSignedOutBanner() {
  const { t } = useI18n();
  const { state, refresh } = useAppState();
  const meta = useMeta();
  const [yt, setYt] = useState<YoutubeStatus | null>(null);
  const out = state?.youtube_signed_out ?? null;
  useEffect(() => {
    if (out)
      api
        .youtube()
        .then(setYt)
        .catch(() => {});
  }, [!!out]); // eslint-disable-line react-hooks/exhaustive-deps
  const c = useYoutubeConnect(yt, setYt);
  if (!out) return null;
  const name = out.channel?.title;
  return (
    <div className="yt-banner" role="status">
      <Icon name="alert" size={15} />
      <span className="yt-banner-text">
        {name
          ? t("ytc.signed_out_banner", { name })
          : t("ytc.signed_out_banner_plain")}
      </span>
      {c.phase === "waiting" ? (
        <>
          <span
            className="spinner"
            style={{ width: 12, height: 12 }}
            aria-hidden="true"
          />
          <span className="muted">{t("ytc.waiting_title")}</span>
          <button className="link-btn" onClick={c.cancel}>
            {t("common.cancel")}
          </button>
        </>
      ) : meta?.is_local === false ? (
        <a href="#/settings">{t("nav.settings")}</a>
      ) : (
        <button
          className="btn btn-sm btn-primary"
          onClick={c.start}
          disabled={!yt}
        >
          <GoogleG size={14} />
          {t("ytc.reconnect")}
        </button>
      )}
      <button
        className="btn btn-ghost icon-btn"
        aria-label={t("ytc.dismiss")}
        onClick={() =>
          api
            .youtubeDismissSignedOut()
            .then(() => refresh())
            .catch(() => {})
        }
      >
        <Icon name="x" size={14} />
      </button>
      {c.phase === "tip" && (
        <WarningTip
          onClose={c.closeTip}
          onGo={(remember) => {
            if (remember) setTipSeen();
            c.open();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Settings: Google review status

export function VerificationStatus({ yt }: { yt: YoutubeStatus }) {
  const { t, num } = useI18n();
  const [more, setMore] = useState(false);
  if (yt.mode !== "shared") return null;
  const v = yt.shared.verification;
  const n = num(yt.shared.user_cap);
  return (
    <div className={`ytc-verif v-${v}`}>
      <div className="ytc-verif-row">
        <span className="ytc-verif-dot" aria-hidden="true" />
        <span>
          <b>{t("ytc.verif_title")}:</b> {t(`ytc.verif.${v}`, { n })}
          {v !== "verified" && (
            <>
              {" "}
              <button
                className="link-btn"
                onClick={() => setMore(!more)}
                aria-expanded={more}
              >
                {t("ytc.verif_more")}
              </button>
            </>
          )}
        </span>
      </div>
      {more && <p className="muted ytc-sub">{t("ytc.verif_explain", { n })}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- Advanced: own Google project

const STEPS = [
  { key: "s1", link: `${CONSOLE}/projectcreate`, sketch: "project" },
  {
    key: "s2",
    link: `${CONSOLE}/apis/library/youtube.googleapis.com`,
    sketch: "api",
  },
  {
    key: "s3",
    link: `${CONSOLE}/auth/overview`,
    sketch: "consent",
    link2: `${CONSOLE}/auth/audience`,
  },
  { key: "s4", link: `${CONSOLE}/auth/clients/create`, sketch: "client" },
  { key: "s5", link: null, sketch: "load" },
] as const;

export function AdvancedWizard({
  yt,
  onStatus,
  onClose,
  initialStep = 0,
}: {
  yt: YoutubeStatus;
  onStatus: (s: YoutubeStatus) => void;
  onClose: () => void;
  initialStep?: number;
}) {
  const { t, num } = useI18n();
  const [i, setI] = useState(initialStep);
  const head = useRef<HTMLHeadingElement>(null);
  useEffect(() => head.current?.focus(), [i]);
  const s = STEPS[i];
  const n = STEPS.length;
  return (
    <section className="ytw" aria-labelledby="ytw-title">
      <div className="ytw-top">
        <span className="ytw-count">
          {t("ytc.adv_progress", { i: num(i + 1), n: num(n) })}
        </span>
        <button
          className="btn btn-ghost icon-btn"
          onClick={onClose}
          aria-label={t("common.close")}
        >
          <Icon name="x" size={14} />
        </button>
      </div>
      <div
        className="ytw-bar"
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={n}
        aria-valuenow={i + 1}
        aria-label={t("ytc.adv_progress", { i: i + 1, n })}
      >
        <span style={{ width: `${((i + 1) / n) * 100}%` }} />
      </div>
      <h3 id="ytw-title" className="ytw-title" tabIndex={-1} ref={head}>
        {t(`ytc.adv.${s.key}_title`)}
      </h3>
      <Sketch kind={s.sketch} />
      <p className="ytw-body">{t(`ytc.adv.${s.key}_body`)}</p>
      {s.link && (
        <div className="ytc-row">
          <a
            className="btn btn-sm btn-primary"
            href={s.link}
            target="_blank"
            rel="noreferrer"
          >
            <Icon name="link" />
            {t("ytc.adv_open")}
          </a>
          {"link2" in s && (
            <a
              className="btn btn-sm"
              href={s.link2}
              target="_blank"
              rel="noreferrer"
            >
              <Icon name="link" />
              {t("ytc.adv_open_audience")}
            </a>
          )}
        </div>
      )}
      {s.key !== "s5" ? (
        <p className="ytw-check">
          <Icon name="check" size={14} />
          <span>
            <b>{t("ytc.check_label")}</b> {t(`ytc.adv.${s.key}_check`)}
          </span>
        </p>
      ) : (
        <LoadClient yt={yt} onStatus={onStatus} onApiOff={() => setI(1)} />
      )}
      <div className="ytw-foot">
        {i > 0 ? (
          <button className="btn btn-ghost" onClick={() => setI(i - 1)}>
            <Icon name="chevron-left" className="icon flip-rtl" />
            {t("onb.back")}
          </button>
        ) : (
          <span />
        )}
        {i < n - 1 && (
          <button className="btn btn-primary" onClick={() => setI(i + 1)}>
            {t("ytc.adv_done_step")}
            <Icon name="chevron-right" className="icon flip-rtl" />
          </button>
        )}
      </div>
    </section>
  );
}

function LoadClient({
  yt,
  onStatus,
  onApiOff,
}: {
  yt: YoutubeStatus;
  onStatus: (s: YoutubeStatus) => void;
  onApiOff: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [text, setText] = useState("");
  const [check, setCheck] = useState<null | {
    ok: boolean;
    error?: string;
    hint?: string | null;
    project_id?: string | null;
  }>(null);
  const [drag, setDrag] = useState(false);
  const [saving, setSaving] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const c = useYoutubeConnect(yt, onStatus);

  useEffect(() => {
    if (!text.trim()) return setCheck(null);
    const id = window.setTimeout(
      () =>
        api
          .youtubeClientCheck(text)
          .then(setCheck)
          .catch(() => {}),
      250,
    );
    return () => window.clearTimeout(id);
  }, [text]);
  useEffect(() => {
    if (c.flow?.status === "api_disabled") onApiOff();
  }, [c.flow?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const readFile = async (f: File | undefined) => {
    if (!f) return;
    if (f.size > 64 * 1024) {
      setCheck({ ok: false, error: t("ytc.file_too_big") });
      return;
    }
    setText(await f.text());
  };
  const save = async () => {
    setSaving(true);
    try {
      const s = await api.youtubeClient(text);
      onStatus(s);
      c.open(); // own project: the user made the app, no warning tip needed
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setSaving(false);
  };

  if (yt.connected && yt.mode === "own")
    return (
      <p className="ytw-check ok">
        <Icon name="check" size={14} />
        <span>{t("ytc.own_connected", { name: yt.channel?.title ?? "" })}</span>
      </p>
    );
  return (
    <div className="ytw-load">
      <div
        className={`ytw-drop${drag ? " drag" : ""}${check?.ok ? " ok" : check ? " bad" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          readFile(e.dataTransfer.files?.[0]);
        }}
      >
        <Icon name="file" size={22} />
        <b>{t("ytc.drop")}</b>
        <span className="muted">{t("ytc.drop_or")}</span>
        <button className="btn btn-sm" onClick={() => file.current?.click()}>
          {t("ytc.choose_file")}
        </button>
        <input
          ref={file}
          type="file"
          hidden
          accept=".json,application/json"
          onChange={(e) => {
            readFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
      <label className="field">
        <span className="field-label">{t("ytc.paste_label")}</span>
        <textarea
          className="input mono"
          rows={3}
          dir="ltr"
          spellCheck={false}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='{"installed":{"client_id":"….apps.googleusercontent.com", …}}'
          aria-describedby="ytw-json-state"
        />
      </label>
      <div id="ytw-json-state" aria-live="polite">
        {check?.ok && (
          <p className="ytw-check ok">
            <Icon name="check" size={14} />
            <span>
              {t("ytc.json_ok", { project: check.project_id ?? "?" })}
            </span>
          </p>
        )}
        {check && !check.ok && (
          <div className="notice notice-warn">
            <Icon name="alert" />
            <span>
              <b>{check.error}</b> {check.hint}
            </span>
          </div>
        )}
      </div>
      {c.phase === "waiting" ? (
        <Waiting url={c.url} since={c.since} own onCancel={c.cancel} />
      ) : (
        <>
          <button
            className="gbtn"
            onClick={save}
            disabled={!check?.ok || saving}
          >
            <span className="gbtn-g">
              <GoogleG />
            </span>
            <span>{t("ytc.save_connect")}</span>
          </button>
          <FlowResult
            flow={c.flow}
            onRetry={c.open}
            onDismiss={c.clearFlow}
            projectId={yt.project_id}
          />
        </>
      )}
    </div>
  );
}

/** One small drawing per wizard step: the Console page with the thing to click marked. */
function Sketch({ kind }: { kind: (typeof STEPS)[number]["sketch"] }) {
  const { t } = useI18n();
  const field = (y: number, label: string, w = 150) => (
    <g>
      <text x="24" y={y - 6} className="sk-label">
        {label}
      </text>
      <rect x="24" y={y} width={w} height="18" rx="4" className="sk-field" />
    </g>
  );
  const hot = (x: number, y: number, w: number, label: string) => (
    <g>
      <rect
        x={x - 4}
        y={y - 4}
        width={w + 8}
        height="30"
        rx="10"
        className="ill-ring"
      />
      <rect x={x} y={y} width={w} height="22" rx="6" className="sk-btn" />
      <text x={x + w / 2} y={y + 15} textAnchor="middle" className="sk-btn-t">
        {label}
      </text>
    </g>
  );
  let body: ReactNode = null;
  if (kind === "project")
    body = (
      <>
        <text x="24" y="44" className="sk-h">
          {t("ytc.ill.new_project")}
        </text>
        {field(72, t("ytc.ill.project_name"))}
        <text x="30" y="84.5" className="sk-val">
          SharkyClips
        </text>
        {hot(24, 104, 70, t("ytc.ill.create"))}
      </>
    );
  else if (kind === "api")
    body = (
      <>
        <rect x="24" y="34" width="34" height="24" rx="5" className="sk-yt" />
        <path d="M37 40v12l9-6z" className="sk-yt-play" />
        <text x="66" y="51" className="sk-h">
          YouTube Data API v3
        </text>
        <rect
          x="24"
          y="68"
          width="170"
          height="6"
          rx="3"
          className="ill-line"
        />
        {hot(24, 92, 80, t("ytc.ill.enable"))}
      </>
    );
  else if (kind === "consent")
    body = (
      <>
        <text x="24" y="44" className="sk-h">
          Google Auth Platform
        </text>
        {field(66, t("ytc.ill.app_name"), 120)}
        <text x="30" y="78.5" className="sk-val">
          SharkyClips
        </text>
        {field(102, t("ytc.ill.test_users"), 120)}
        <text x="30" y="114.5" className="sk-val">
          you@gmail.com
        </text>
        {hot(170, 98, 92, t("ytc.ill.publish_app"))}
      </>
    );
  else if (kind === "client")
    body = (
      <>
        <text x="24" y="44" className="sk-h">
          {t("ytc.ill.create_client")}
        </text>
        {field(66, t("ytc.ill.app_type"), 120)}
        <text x="30" y="78.5" className="sk-val">
          {t("ytc.ill.desktop_app")}
        </text>
        {hot(24, 98, 110, t("ytc.ill.download"))}
      </>
    );
  else
    body = (
      <>
        <g transform="translate(40 40)">
          <path d="M0 0h34l12 12v50H0z" className="sk-file" />
          <path d="M34 0v12h12" className="sk-file-fold" />
          <text x="23" y="42" textAnchor="middle" className="sk-file-t">
            JSON
          </text>
        </g>
        <path d="M108 72h60M158 64l10 8-10 8" className="sk-arrow" />
        <g transform="translate(186 44)">
          <rect width="76" height="56" rx="10" className="sk-app" />
          <path
            d="M20 40C24 30 32 18 50 12 44 20 42 30 48 40Z"
            className="sk-fin"
          />
        </g>
      </>
    );
  return (
    <svg className="ytw-sketch" viewBox="0 0 290 140" aria-hidden="true">
      <rect
        x="1"
        y="1"
        width="288"
        height="138"
        rx="12"
        className="ill-frame"
      />
      <rect x="1" y="1" width="288" height="18" rx="12" className="ill-bar" />
      {body}
    </svg>
  );
}

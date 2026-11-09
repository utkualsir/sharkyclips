// 1.2.36 Settings → Accounts: YouTube, Instagram and TikTok side by side (connect, reconnect,
// disconnect, who is connected, a status pill, the quota) with a guided setup for your own
// Meta / TikTok developer app. Also opened inline from the Publish dialog.
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api, type YoutubeStatus } from "../api";
import { useI18n } from "../i18n";
import { accountsApi, TARGET_NAME, type Account, type Accounts, type Quota, type Target } from "../multipost";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { PlatformIcon } from "./PlatformIcons";
import { CopyButton, Modal } from "./ui";
import { ConnectYoutube, YoutubeAccount } from "./YoutubeConnect";

const LINKS = {
  tt_apps: "https://developers.tiktok.com/apps/",
  tt_docs: "https://developers.tiktok.com/doc/content-posting-api-get-started",
  tt_private: "https://support.tiktok.com/en/account-and-privacy/account-privacy-settings/making-your-account-public-or-private",
  meta_apps: "https://developers.facebook.com/apps/",
  meta_docs: "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login",
  ig_invites: "https://www.instagram.com/accounts/manage_access/",
  site_terms: "https://utkualsir.github.io/sharkyclips-site/terms.html",
  site_privacy: "https://utkualsir.github.io/sharkyclips-site/privacy.html",
};

let cache: Promise<Accounts> | null = null;
/** The three accounts (shared by every Publish button on the screen; reload() refreshes). */
export function useAccounts(): [Accounts | null, () => void] {
  const [a, setA] = useState<Accounts | null>(null);
  const reload = useCallback(() => {
    cache = accountsApi.list();
    cache.then(setA).catch(() => (cache = null));
  }, []);
  useEffect(() => {
    cache = cache ?? accountsApi.list();
    cache.then(setA).catch(() => (cache = null));
    const on = () => reload();
    window.addEventListener("sc-accounts", on);
    return () => window.removeEventListener("sc-accounts", on);
  }, [reload]);
  return [a, reload];
}

/** Tell every account view on the screen to load again (after a connect / disconnect). */
export function accountsChanged() {
  cache = null;
  window.dispatchEvent(new Event("sc-accounts"));
}

export function StatusPill({ a }: { a: Account | undefined }) {
  const { t } = useI18n();
  const pill = a?.health.pill ?? "signed_out";
  const reason = a?.health.reason;
  const text =
    pill === "ok"
      ? t("acc.pill_ok")
      : pill === "attention"
        ? t(`acc.pill_attention_${reason === "expires" ? "expires" : reason === "scope" ? "scope" : reason === "no_channel" ? "no_channel" : "other"}`)
        : t(reason === "signed_out" ? "acc.pill_signed_out" : "acc.pill_not_connected");
  return (
    <span className={`acc-pill acc-pill-${pill}`}>
      <span className="acc-dot" aria-hidden="true" />
      {text}
    </span>
  );
}

function Avatar({ a }: { a: Account }) {
  const [broken, setBroken] = useState(false);
  if (a.avatar && !broken)
    return <img className="acc-avatar" src={accountsApi.avatar(a.platform, a.connected_at ?? "")} alt="" onError={() => setBroken(true)} />;
  return (
    <span className={`acc-avatar acc-avatar-ph pf-bg-${a.platform}`} aria-hidden="true">
      {(a.handle || "?").replace(/^@/, "").slice(0, 1).toUpperCase()}
    </span>
  );
}

function QuotaLine({ p, q }: { p: Target; q: Quota | null | undefined }) {
  const { t, num } = useI18n();
  if (!q) return null;
  if (p === "youtube")
    return <span className="acc-quota">{t("acc.quota_youtube", { n: num(q.uploads_left ?? 0) })}</span>;
  return (
    <span className="acc-quota">
      {t(q.approx ? "acc.quota_posts_approx" : "acc.quota_posts", { used: num(q.used), total: num(q.total) })}
    </span>
  );
}

function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="acc-step">
      <span className="acc-step-n" aria-hidden="true">
        {n}
      </span>
      <div>{children}</div>
    </li>
  );
}

function Ext({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="acc-link">
      {children} <Icon name="link" size={12} />
    </a>
  );
}

function TikTokSetup({ a, onDone }: { a: Account; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [redirect, setRedirect] = useState("");
  const [key, setKey] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState(false);
  useEffect(() => {
    accountsApi.tiktokRedirect().then((r) => setRedirect(r.redirect_uri)).catch(() => {});
  }, []);
  // the sign-in finishes in the browser tab: look for the new account
  useEffect(() => {
    if (!waiting) return;
    const iv = window.setInterval(async () => {
      const x = await accountsApi.list().catch(() => null);
      if (x?.tiktok.connected && x.tiktok.health.pill !== "signed_out") {
        setWaiting(false);
        toast({ kind: "ok", text: t("acc.connected_toast", { name: "TikTok", handle: x.tiktok.handle ?? "" }) });
        onDone();
      }
    }, 2000);
    const stop = window.setTimeout(() => setWaiting(false), 10 * 60 * 1000);
    return () => {
      window.clearInterval(iv);
      window.clearTimeout(stop);
    };
  }, [waiting]); // eslint-disable-line react-hooks/exhaustive-deps
  const go = async () => {
    setBusy(true);
    try {
      const r = await accountsApi.tiktokConnect(key.trim(), secret.trim());
      window.open(r.url, "_blank", "noopener");
      setWaiting(true);
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  const reuse = a.has_app && !key && !secret;
  return (
    <div className="acc-setup">
      {(() => {
        const steps = (
        <ol className="acc-steps">
          <Step n={1}>
            {t("acc.tt_s1")} <Ext href={LINKS.tt_apps}>developers.tiktok.com</Ext>
          </Step>
          <Step n={2}>
            {t("acc.tt_s2")}
            <span className="acc-hint">
              {t("acc.tt_s2_urls")} <Ext href={LINKS.site_terms}>{t("acc.terms")}</Ext> · <Ext href={LINKS.site_privacy}>{t("acc.privacy")}</Ext>
            </span>
          </Step>
          <Step n={3}>{t("acc.tt_s3")}</Step>
          <Step n={4}>
            {t("acc.tt_s4")}
            <code className="acc-code">user.info.basic, video.publish, video.list</code>
          </Step>
          <Step n={5}>
            {t("acc.tt_s5")}
            <span className="acc-copy">
              <code className="acc-code">{redirect || "…"}</code>
              {redirect && <CopyButton text={redirect} />}
            </span>
          </Step>
          <Step n={6}>{t("acc.tt_s6")}</Step>
          <Step n={7}>
            {t("acc.tt_s7")} <Ext href={LINKS.tt_private}>{t("acc.how")}</Ext>
          </Step>
          <Step n={8}>{t("acc.tt_s8")}</Step>
        </ol>
        );
        return reuse ? (
          <details className="acc-adv acc-guide">
            <summary>{t("acc.guide")}</summary>
            {steps}
          </details>
        ) : (
          steps
        );
      })()}
      <div className="acc-form">
        <label className="field">
          <span className="field-label">Client key</span>
          <input className="input mono" value={key} autoComplete="off" spellCheck={false}
            placeholder={reuse ? t("acc.keep_saved") : ""} onChange={(e) => setKey(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Client secret</span>
          <input className="input mono" type="password" value={secret} autoComplete="off"
            placeholder={reuse ? t("acc.keep_saved") : ""} onChange={(e) => setSecret(e.target.value)} />
        </label>
      </div>
      <button className="btn btn-primary" disabled={busy || waiting || (!reuse && (!key.trim() || !secret.trim()))} onClick={go}>
        {busy || waiting ? <span className="spinner" /> : <PlatformIcon p="tiktok" size={16} />}{" "}
        {waiting ? t("acc.waiting_browser") : t(a.has_app ? "acc.reconnect_with" : "acc.connect_with", { name: "TikTok" })}
      </button>
      {waiting && <p className="acc-hint">{t("acc.waiting_hint")}</p>}
    </div>
  );
}

function InstagramSetup({ a, onDone }: { a: Account; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [adv, setAdv] = useState(false);
  const [appId, setAppId] = useState("");
  const [secret, setSecret] = useState("");
  const [redirect, setRedirect] = useState("");
  const [pasted, setPasted] = useState("");
  const [started, setStarted] = useState(false);
  useEffect(() => {
    accountsApi.igRedirect().then((r) => setRedirect(r.redirect_uri)).catch(() => {});
  }, []);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      const x = await accountsApi.list();
      toast({ kind: "ok", text: t("acc.connected_toast", { name: "Instagram", handle: x.reels.handle ?? "" }) });
      onDone();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    setBusy(false);
  };
  return (
    <div className="acc-setup">
      <ol className="acc-steps">
        <Step n={1}>{t("acc.ig_s1")}</Step>
        <Step n={2}>
          {t("acc.ig_s2")} <Ext href={LINKS.meta_apps}>developers.facebook.com/apps</Ext>
        </Step>
        <Step n={3}>{t("acc.ig_s3")}</Step>
        <Step n={4}>{t("acc.ig_s4")}</Step>
        <Step n={5}>
          {t("acc.ig_s5")} <Ext href={LINKS.ig_invites}>{t("acc.ig_s5_link")}</Ext>
        </Step>
        <Step n={6}>
          {t("acc.ig_s6")}
          <code className="acc-code">instagram_business_basic, instagram_business_content_publish, instagram_business_manage_insights</code>
        </Step>
      </ol>
      <label className="field">
        <span className="field-label">{t("acc.ig_token")}</span>
        <input className="input mono" type="password" value={token} autoComplete="off" spellCheck={false}
          placeholder="IGAA…" onChange={(e) => setToken(e.target.value)} />
        <span className="field-hint">{t("acc.ig_token_hint")}</span>
      </label>
      <button className="btn btn-primary" disabled={busy || token.trim().length < 20} onClick={() => run(() => accountsApi.igToken(token.trim()))}>
        {busy ? <span className="spinner" /> : <PlatformIcon p="reels" size={16} />} {t("acc.connect_with", { name: "Instagram" })}
      </button>
      <details className="acc-adv" open={adv} onToggle={(e) => setAdv((e.target as HTMLDetailsElement).open)}>
        <summary>{t("acc.ig_adv")}</summary>
        <p className="acc-hint">{t("acc.ig_adv_body")}</p>
        <span className="acc-copy">
          <code className="acc-code">{redirect || "…"}</code>
          {redirect && <CopyButton text={redirect} />}
        </span>
        <div className="acc-form">
          <label className="field">
            <span className="field-label">{t("acc.ig_app_id")}</span>
            <input className="input mono" value={appId} autoComplete="off" placeholder={a.has_app ? t("acc.keep_saved") : ""}
              onChange={(e) => setAppId(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">{t("acc.ig_app_secret")}</span>
            <input className="input mono" type="password" value={secret} autoComplete="off" onChange={(e) => setSecret(e.target.value)} />
          </label>
        </div>
        <button
          className="btn"
          disabled={busy || (!a.has_app && (!appId.trim() || !secret.trim()))}
          onClick={async () => {
            try {
              const r = await accountsApi.igOauth(appId.trim(), secret.trim());
              window.open(r.url, "_blank", "noopener");
              setStarted(true);
            } catch (e: any) {
              toast({ kind: "err", text: e.message, hint: e.hint });
            }
          }}
        >
          <Icon name="link" /> {t("acc.ig_open_login")}
        </button>
        {started && (
          <>
            <label className="field">
              <span className="field-label">{t("acc.ig_paste")}</span>
              <input className="input mono" value={pasted} autoComplete="off" spellCheck={false} placeholder="https://localhost:…?code=…"
                onChange={(e) => setPasted(e.target.value)} />
            </label>
            <button className="btn btn-primary" disabled={busy || !pasted.includes("code=")} onClick={() => run(() => accountsApi.igFinish(pasted.trim()))}>
              <Icon name="check" /> {t("acc.ig_finish")}
            </button>
          </>
        )}
      </details>
    </div>
  );
}

function SocialCard({ a, quota, onChange }: { a: Account; quota: Quota | null | undefined; onChange: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const p = a.platform as "tiktok" | "reels";
  const [setup, setSetup] = useState(!a.connected);
  useEffect(() => setSetup(!a.connected), [a.connected]);
  const disconnect = async () => {
    if (!window.confirm(t("acc.disconnect_q", { name: TARGET_NAME[p] }))) return;
    try {
      await accountsApi.disconnect(p);
      accountsChanged();
      onChange();
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  const check = async () => {
    try {
      await accountsApi.check(p);
      toast({ kind: "ok", text: t("acc.check_ok") });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
    accountsChanged();
    onChange();
  };
  return (
    <article className={`card acc-card pf-accent-${p}`} aria-labelledby={`acc-${p}`}>
      <header className="acc-head">
        <PlatformIcon p={p} size={22} />
        <h3 id={`acc-${p}`}>{TARGET_NAME[p]}</h3>
        <StatusPill a={a} />
      </header>
      {a.connected && (
        <div className="acc-who">
          <Avatar a={a} />
          <div className="acc-who-text">
            <b dir="auto">{a.handle ? `@${a.handle.replace(/^@/, "")}` : t("acc.connected")}</b>
            {a.name && a.name !== a.handle && <span className="muted" dir="auto">{a.name}</span>}
            <span className="acc-meta">
              <Icon name="lock" size={12} /> {t("acc.encrypted")}
            </span>
            <QuotaLine p={p} q={quota} />
          </div>
        </div>
      )}
      {a.connected && a.health.pill !== "ok" && (
        <p className="acc-note acc-note-warn" role="note">
          <Icon name="alert" size={14} /> {a.health.message || t(`acc.why_${a.health.reason === "expires" ? "expires" : a.health.reason === "scope" ? "scope" : "attention"}`, { name: TARGET_NAME[p] })}
        </p>
      )}
      {p === "tiktok" && a.connected && !a.audited && (
        <p className="acc-note" role="note">
          <Icon name="eye" size={14} /> {t("acc.tt_unaudited")}
        </p>
      )}
      {p === "reels" && a.connected && !a.audited && (
        <p className="acc-note" role="note">
          <Icon name="eye" size={14} /> {t("acc.ig_dev_mode")}
        </p>
      )}
      {a.connected && (
        <div className="acc-actions">
          <button className="btn btn-sm" onClick={() => setSetup((v) => !v)} aria-expanded={setup}>
            <Icon name="refresh" /> {t("acc.reconnect")}
          </button>
          <button className="btn btn-sm btn-ghost" onClick={check}>
            <Icon name="check" /> {t("acc.check")}
          </button>
          <button className="btn btn-sm btn-ghost btn-danger-text" onClick={disconnect}>
            <Icon name="power" /> {t("acc.disconnect")}
          </button>
        </div>
      )}
      {a.connected && (
        <label className="acc-audit">
          <input
            type="checkbox"
            checked={a.audited}
            onChange={async (e) => {
              await accountsApi.setAudited(p, e.target.checked).catch(() => {});
              accountsChanged();
              onChange();
            }}
          />
          <span>{t(p === "tiktok" ? "acc.audited_tiktok" : "acc.audited_reels")}</span>
        </label>
      )}
      {setup &&
        (p === "tiktok" ? (
          <TikTokSetup a={a} onDone={() => (accountsChanged(), onChange())} />
        ) : (
          <InstagramSetup a={a} onDone={() => (accountsChanged(), onChange())} />
        ))}
    </article>
  );
}

function YoutubeCard({ a, quota, onChange }: { a: Account; quota: Quota | null | undefined; onChange: () => void }) {
  const { t } = useI18n();
  const [yt, setYt] = useState<YoutubeStatus | null>(null);
  useEffect(() => {
    api.youtube().then(setYt).catch(() => {});
  }, [a.connected]);
  const status = (s: YoutubeStatus) => {
    setYt(s);
    accountsChanged();
    onChange();
  };
  return (
    <article className="card acc-card pf-accent-youtube" aria-labelledby="acc-youtube">
      <header className="acc-head">
        <PlatformIcon p="youtube" size={22} />
        <h3 id="acc-youtube">YouTube</h3>
        <StatusPill a={a} />
      </header>
      {yt?.connected ? (
        <>
          <YoutubeAccount yt={yt} onStatus={status} onDisconnect={() => api.youtubeDisconnect().then(status).catch(() => {})} />
          <span className="acc-meta">
            <Icon name="lock" size={12} /> {t("acc.encrypted")} · <QuotaLine p="youtube" q={quota} />
          </span>
        </>
      ) : (
        <div className="acc-setup">
          <p className="muted" style={{ margin: 0 }}>{t("acc.yt_body")}</p>
          <ConnectYoutube yt={yt} onStatus={status} />
        </div>
      )}
    </article>
  );
}

/** The three cards. */
export function AccountsGrid({ only }: { only?: Target }) {
  const [a, reload] = useAccounts();
  if (!a)
    return (
      <div className="acc-grid">
        {[0, 1, 2].map((i) => (
          <div key={i} className="card skeleton" style={{ height: 160 }} />
        ))}
      </div>
    );
  const show = (p: Target) => !only || only === p;
  return (
    <div className={`acc-grid${only ? " acc-grid-one" : ""}`}>
      {show("youtube") && <YoutubeCard a={a.youtube} quota={a.quota?.youtube} onChange={reload} />}
      {show("reels") && <SocialCard a={a.reels} quota={a.quota?.reels} onChange={reload} />}
      {show("tiktok") && <SocialCard a={a.tiktok} quota={a.quota?.tiktok} onChange={reload} />}
    </div>
  );
}

/** Settings section "Accounts" (Pro and Easy). */
export function AccountsSection({ className = "card setting acc-section" }: { className?: string }) {
  const { t } = useI18n();
  return (
    <section className={className} id="accounts" aria-labelledby="acc-title">
      <div>
        <h2 id="acc-title">{t("acc.title")}</h2>
        <p>{t("acc.lede")}</p>
      </div>
      <AccountsGrid />
    </section>
  );
}

/** Connect one platform without leaving the Publish dialog. */
export function ConnectDialog({ p, onClose }: { p: Target; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Modal title={t("acc.connect_title", { name: TARGET_NAME[p] })} onClose={onClose} top wide>
      <AccountsGrid only={p} />
    </Modal>
  );
}

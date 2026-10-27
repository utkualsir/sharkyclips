// LAN access PIN: the login screen other devices see, and the PIN box in Settings.
// Backend: backend/sharkyclips/web/auth.py. The computer running SharkyClips never logs in.
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api, AUTH_EVENT, type AuthStatus } from "../api";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { BrandMark } from "./Brand";
import { Icon } from "./Icons";

/** Shows the login screen instead of the app when this device needs the access PIN. */
export function LanGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api
      .authStatus()
      .then(setStatus)
      .catch(() => setFailed(true)); // old server or offline: let the app show its own errors
    const onLost = () => setStatus((s) => (s ? { ...s, required: true, authenticated: false } : s));
    window.addEventListener(AUTH_EVENT, onLost);
    return () => window.removeEventListener(AUTH_EVENT, onLost);
  }, []);

  if (failed || (status && (!status.required || status.authenticated))) return <>{children}</>;
  if (!status) return null;
  return <LanLogin kind={status.kind} onDone={() => window.location.reload()} />;
}

function LanLogin({ kind, onDone }: { kind: AuthStatus["kind"]; onDone: () => void }) {
  const { t } = useI18n();
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [wait, setWait] = useState(0);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const errId = useId();

  useEffect(() => {
    if (wait <= 0) return;
    const id = window.setTimeout(() => setWait((w) => w - 1), 1000);
    return () => window.clearTimeout(id);
  }, [wait]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!secret || wait > 0 || busy) return;
    setBusy(true);
    try {
      const res = await api.authLogin(secret);
      if (res.ok) return onDone();
      setError(res.code === "locked" ? t("lan.locked") : t("lan.wrong"));
      setWait(res.retry_after ?? 0);
      setSecret("");
      input.current?.focus();
    } catch {
      setError(t("lan.offline"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="lan-login">
      <form className="card lan-login-card" onSubmit={submit} aria-describedby={error ? errId : undefined}>
        <span className="lan-login-mark" aria-hidden="true">
          <BrandMark size={34} />
        </span>
        <h1 className="display">SharkyClips</h1>
        <p className="muted">{t("lan.login_desc")}</p>
        <label className="field">
          <span className="field-label">{kind === "password" ? t("lan.password") : t("lan.pin")}</span>
          <input
            ref={input}
            className="input"
            type="password"
            inputMode={kind === "password" ? "text" : "numeric"}
            autoComplete="current-password"
            autoFocus
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            aria-invalid={!!error}
          />
        </label>
        {error && (
          <p id={errId} className="lan-login-error" role="alert">
            {error}
            {wait > 0 && ` ${t("lan.wait", { s: wait })}`}
          </p>
        )}
        <button className="btn btn-primary" type="submit" disabled={!secret || wait > 0 || busy}>
          {busy ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <Icon name="check" />}
          {t("lan.login")}
        </button>
      </form>
    </main>
  );
}

/** Settings → Other devices: set, change or remove the access PIN (this computer only). */
export function LanPinBox({ lanOn, isLocal }: { lanOn: boolean; isLocal: boolean }) {
  const { t } = useI18n();
  const toast = useToast();
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [editing, setEditing] = useState(false);
  const [secret, setSecret] = useState("");
  const [show, setShow] = useState(false);
  const inputId = useId();

  useEffect(() => {
    api.authStatus().then(setStatus).catch(() => {});
  }, []);
  if (!status) return null;

  const run = async (fn: () => Promise<AuthStatus>, msg: string) => {
    try {
      setStatus(await fn());
      setEditing(false);
      setSecret("");
      toast({ kind: "ok", text: msg });
    } catch (e: any) {
      toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };

  return (
    <div className="lan-pin">
      {status.enabled ? (
        <div className="sugg">
          <Icon name="check" />
          <span>{status.kind === "password" ? t("lan.password_on") : t("lan.pin_on")}</span>
        </div>
      ) : (
        <div className={`notice${lanOn ? " notice-danger" : ""}`}>
          <Icon name="alert" />
          <span>{lanOn ? t("lan.open_warning") : t("lan.recommend")}</span>
        </div>
      )}
      {!isLocal ? (
        <span className="muted">{t("lan.local_only")}</span>
      ) : editing ? (
        <form
          className="lan-pin-form"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => api.authSetSecret(secret), t("lan.saved"));
          }}
        >
          <label className="field" htmlFor={inputId}>
            <span className="field-label">{t("lan.new")}</span>
          </label>
          <div className="lan-pin-row">
            <input
              id={inputId}
              className="input"
              type={show ? "text" : "password"}
              autoComplete="new-password"
              minLength={4}
              maxLength={128}
              autoFocus
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
            />
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setShow(!show)} aria-pressed={show}>
              {show ? t("lan.hide") : t("lan.show")}
            </button>
          </div>
          <span className="field-hint">{t("lan.rules")}</span>
          <div className="lan-pin-row">
            <button className="btn btn-sm btn-primary" type="submit" disabled={secret.length < 4}>
              {t("lan.save")}
            </button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(false)}>
              {t("lan.cancel")}
            </button>
          </div>
        </form>
      ) : (
        <div className="lan-pin-row">
          <button className={`btn btn-sm${status.enabled ? "" : " btn-primary"}`} onClick={() => setEditing(true)}>
            <Icon name="lock" />
            {status.enabled ? t("lan.change") : t("lan.set")}
          </button>
          {status.enabled && (
            <button className="btn btn-sm btn-ghost" onClick={() => run(api.authClearSecret, t("lan.removed"))}>
              {t("lan.remove")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

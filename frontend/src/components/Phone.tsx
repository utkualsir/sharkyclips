import { useCallback, useEffect, useId, useState } from "react";
import { ApiError, phoneApi, type PhoneStatus, type PhoneView } from "../api";
import { useI18n } from "../i18n";
import { useMeta } from "../meta";
import { useToast } from "../toast";
import { Icon } from "./Icons";
import { LanPinBox } from "./LanAccess";
import { CopyButton, Toggle } from "./ui";

const BOTFATHER = "https://t.me/BotFather";

// =========================================================================== phone (Telegram)

/** Guided Telegram bot setup: 1) create a bot, 2) paste its token, 3) tap Start in the bot. */
export function PhoneConnect({ status, onStatus, compact }: { status: PhoneStatus | null; onStatus: (s: PhoneStatus) => void; compact?: boolean }) {
  const { t } = useI18n();
  const toast = useToast();
  const meta = useMeta();
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const tid = useId();
  const waiting = !!status?.configured && !status.paired;

  useEffect(() => {
    if (!waiting) return;
    let alive = true;
    const tick = () =>
      phoneApi
        .tgPair()
        .then((s) => {
          if (!alive) return;
          onStatus(s);
          if (s.paired) toast({ kind: "ok", text: t("phone.paired_toast") });
        })
        .catch(() => {});
    const iv = window.setInterval(tick, 3000);
    return () => {
      alive = false;
      window.clearInterval(iv);
    };
  }, [waiting, onStatus, toast, t]);

  const call = async (fn: () => Promise<PhoneStatus>, ok?: string) => {
    setBusy(true);
    try {
      onStatus(await fn());
      if (ok) toast({ kind: "ok", text: ok });
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;
  if (status.paired) {
    return (
      <div style={{ display: "grid", gap: 10 }}>
        <div className="sugg">
          <Icon name="check" />
          <span>{t("phone.paired", { bot: `@${status.bot ?? ""}`, name: status.chat || "" })}</span>
        </div>
        <div className="lan-pin-row">
          <button className="btn btn-sm" disabled={busy} onClick={() => call(() => phoneApi.tgTest().then(() => status), t("phone.test_sent"))}>
            {t("phone.test")}
          </button>
          {meta?.is_local && (
            <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => call(() => phoneApi.tgDisconnect())}>
              {t("phone.disconnect")}
            </button>
          )}
        </div>
      </div>
    );
  }
  if (!meta?.is_local) return <span className="muted">{t("lan.local_only")}</span>;
  return (
    <ol className="phone-steps">
      <li className={status.configured ? "done" : ""}>
        <b>{t("phone.step1")}</b>
        {!compact && <span className="muted">{t("phone.step1_body")}</span>}
        <a className="btn btn-sm" href={BOTFATHER} target="_blank" rel="noreferrer">
          <Icon name="link" size={13} /> @BotFather
        </a>
      </li>
      <li className={status.configured ? "done" : ""}>
        <label htmlFor={tid}><b>{t("phone.step2")}</b></label>
        <form
          className="lan-pin-row"
          onSubmit={(e) => {
            e.preventDefault();
            call(() => phoneApi.tgToken(token)).then(() => setToken(""));
          }}
        >
          <input id={tid} className="input mono" dir="ltr" autoComplete="off" spellCheck={false} placeholder="123456789:AA…" value={token} onChange={(e) => setToken(e.target.value)} />
          <button className="btn btn-sm btn-primary" type="submit" disabled={busy || token.trim().length < 30}>
            {t("phone.connect")}
          </button>
        </form>
      </li>
      <li>
        <b>{t("phone.step3")}</b>
        {waiting && status.link ? (
          <>
            <span className="muted">{t("phone.step3_body", { bot: `@${status.bot ?? ""}` })}</span>
            <div className="sugg">
              <Icon name="message" />
              <a className="mono link" dir="ltr" href={status.link} target="_blank" rel="noreferrer" style={{ overflowWrap: "anywhere" }}>
                {status.link}
              </a>
              <CopyButton text={status.link} />
            </div>
            <span className="muted" style={{ fontSize: 12.5 }}>
              {t("phone.code_alt", { code: status.link.split("=").pop() ?? "" })}
            </span>
            <span className="muted phone-wait"><span className="dot" /> {t("phone.waiting")}</span>
          </>
        ) : (
          <span className="muted">{t("phone.step3_later")}</span>
        )}
      </li>
    </ol>
  );
}

/** Pro settings card: Telegram + the approval page on the Wi-Fi (+ Tailscale for away from home). */
export function PhoneCard() {
  const { t } = useI18n();
  const meta = useMeta();
  const toast = useToast();
  const [view, setView] = useState<PhoneView | null>(null);
  useEffect(() => {
    phoneApi.get().then(setView).catch(() => {});
  }, []);
  const onStatus = useCallback((s: PhoneStatus) => setView((v) => (v ? { ...v, ...s } : v)), []);
  const save = async (body: Parameters<typeof phoneApi.set>[0]) => {
    try {
      setView(await phoneApi.set(body));
    } catch (e) {
      if (e instanceof ApiError) toast({ kind: "err", text: e.message, hint: e.hint });
    }
  };
  if (!view) return null;
  const p = view;
  const lan = view.lan;
  return (
    <section className="card setting" id="phone">
      <div>
        <h2>{t("phone.title")}</h2>
        <p>{t("phone.desc")}</p>
      </div>
      <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
        <div className="field">
          <span className="field-label">{t("phone.telegram")}</span>
          <PhoneConnect status={p} onStatus={onStatus} />
        </div>
        {p.paired && (
          <div className="toggle-line">
            <span>
              <b>{t("phone.send")}</b>
              <span className="muted ez-hint">{t("phone.send_hint", { n: p.send_top })}</span>
            </span>
            <Toggle checked={p.send} onChange={(v) => save({ send: v })} label={t("phone.send")} />
          </div>
        )}
        <div className="field">
          <span className="field-label">{t("phone.page")}</span>
          <span className="field-hint" style={{ marginTop: 0 }}>{t("phone.page_desc")}</span>
          {meta?.is_local && (
            <div className="toggle-line">
              <span>
                <b>{t("phone.page_switch")}</b>
                <span className="muted ez-hint">{lan.pin ? t("phone.page_pin_ok") : t("phone.page_needs_pin")}</span>
              </span>
              <Toggle checked={lan.enabled} onChange={(v) => save({ lan: v })} label={t("phone.page_switch")} />
            </div>
          )}
          {!lan.pin && meta?.is_local && <LanPinBox lanOn={lan.active} isLocal />}
          {lan.enabled && lan.pin && !lan.active && (
            <div className="notice">
              <Icon name="refresh" />
              <span>{lan.busy ? t("phone.restart_busy") : t("phone.restart_needed")}</span>
              {!lan.busy && (
                <button
                  className="btn btn-sm"
                  onClick={() =>
                    phoneApi
                      .restart()
                      .then((r) => toast({ kind: r.restarting ? "ok" : "info", text: r.restarting ? t("phone.restarting") : t("phone.restart_manual") }))
                      .catch(() => {})
                  }
                >
                  {t("phone.restart")}
                </button>
              )}
            </div>
          )}
          {lan.active && lan.approve_url && (
            <div className="sugg">
              <Icon name="globe" />
              <a className="mono link" dir="ltr" href={lan.approve_url} target="_blank" rel="noreferrer" style={{ overflowWrap: "anywhere" }}>
                {lan.approve_url}
              </a>
              <CopyButton text={lan.approve_url} />
            </div>
          )}
          <details className="phone-guide">
            <summary>{t("phone.away")}</summary>
            <ol>
              <li>{t("phone.away1")}</li>
              <li>{t("phone.away2")}</li>
              <li>{t("phone.away3")}</li>
              <li>{t("phone.away4")}</li>
            </ol>
            <p className="muted">{t("phone.away_note")}</p>
          </details>
        </div>
      </div>
    </section>
  );
}

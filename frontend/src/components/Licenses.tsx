// 1.2.19: credit lines for the AI models (with links), the About & licenses card, and the
// "AI voice" switches of a dubbed upload.
import { useEffect, useState } from "react";
import { aboutApi, type AiVoiceInfo, type LicensesView, type ModelLicense } from "../extras";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";
import { Toggle } from "./ui";

function Ext({ href, children }: { href?: string; children: React.ReactNode }) {
  if (!href) return <>{children}</>;
  return (
    <a href={href} target="_blank" rel="noreferrer" dir="ltr">
      {children}
    </a>
  );
}

/** A translated sentence with {a} / {b} ... replaced by links (keeps each language's word order). */
function Linked({ text, links }: { text: string; links: Record<string, { by: string; url?: string }> }) {
  const parts = text.split(/\{(\w+)\}/);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 && links[p] ? (
          <Ext key={i} href={links[p].url}>
            {links[p].by}
          </Ext>
        ) : (
          <span key={i}>{p}</span>
        ),
      )}
    </>
  );
}

/** "Pocket TTS · Kyutai · CC-BY-4.0 · project page", plus what was changed and by whom. */
export function LicenseList({ items }: { items: ModelLicense[] }) {
  const { t } = useI18n();
  return (
    <ul className="license-list">
      {items.map((l) => (
        <li key={l.name}>
          <span dir="ltr">
            <b>{l.name}</b> · {l.by} · <Ext href={l.license_url}>{l.license}</Ext>
          </span>
          {l.source_url && (
            <>
              {" · "}
              <Ext href={l.source_url}>{t("lic.original")}</Ext>
            </>
          )}
          {l.changes && l.chain && (
            <span className="muted license-change">
              <Linked text={t(`lic.changes.${l.changes}`)} links={{ a: l.chain[0], b: l.chain[1] ?? l.chain[0] }} />
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/** Settings: the app's version and license, and the licenses of the optional AI models. */
export function AboutCard({ easy }: { easy?: boolean }) {
  const { t } = useI18n();
  const [data, setData] = useState<LicensesView | null>(null);
  useEffect(() => {
    aboutApi.licenses().then(setData).catch(() => {});
  }, []);
  const body = (
    <div style={{ display: "grid", gap: 10, alignContent: "start" }}>
      {data?.groups.map((g) => (
        <div key={g.id}>
          <span className="field-label">{t(`about.group.${g.id}`)}</span>
          <LicenseList items={g.items} />
        </div>
      ))}
    </div>
  );
  const intro = data ? t("about.desc", { v: data.app.version, license: data.app.license }) : "";
  if (easy)
    return (
      <section className="card ez-set-card" id="about" aria-labelledby="ez-set-about">
        <h2 id="ez-set-about">{t("about.title")}</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          {intro}
        </p>
        {body}
      </section>
    );
  return (
    <section className="card setting" id="about">
      <div>
        <h2>{t("about.title")}</h2>
        <p>{intro}</p>
      </div>
      {body}
    </section>
  );
}

/** The two switches a dubbed upload shows (both on unless the user turns them off). */
export function AiVoiceSwitches({
  info,
  note,
  synthetic,
  onNote,
  onSynthetic,
}: {
  info: Pick<AiVoiceInfo, "dub" | "line">;
  note: boolean;
  synthetic: boolean;
  onNote: (v: boolean) => void;
  onSynthetic: (v: boolean) => void;
}) {
  const { t } = useI18n();
  if (!info.dub) return null;
  return (
    <div className="field ai-voice-box">
      <span className="field-label">
        <Icon name="mic" size={14} /> {t("aivoice.title")}
      </span>
      <span className="field-hint">{t("aivoice.body")}</span>
      <div className="toggle-row">
        <Toggle checked={note} onChange={onNote} label={t("aivoice.note")} />
        <span>{t("aivoice.note")}</span>
      </div>
      {note && info.line && (
        <span className="field-hint ai-voice-line" dir="auto">
          “{info.line}”
        </span>
      )}
      <div className="toggle-row">
        <Toggle checked={synthetic} onChange={onSynthetic} label={t("aivoice.synthetic")} />
        <span>{t("aivoice.synthetic")}</span>
      </div>
      <span className="field-hint">{t("aivoice.synthetic_hint")}</span>
    </div>
  );
}

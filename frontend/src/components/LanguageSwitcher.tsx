import { useEffect, useId, useRef, useState } from "react";
import { UI_LANGUAGES, useI18n } from "../i18n";
import { chooseLanguage } from "../meta";
import { Flag } from "./Flags";

export { Flag };


export function LanguageSwitcher({ compact, big }: { compact?: boolean; big?: boolean }) {
  const { t, lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const id = useId();
  const cur = UI_LANGUAGES.find((l) => l.code === lang) ?? UI_LANGUAGES[0];

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    window.addEventListener("mousedown", close);
    list.current?.querySelector<HTMLButtonElement>('[aria-current="true"]')?.focus({ preventScroll: true });
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  const pick = (code: string) => {
    chooseLanguage(code, setLang);
    setOpen(false);
  };
  const onListKey = (e: React.KeyboardEvent) => {
    const items = Array.from(list.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
    const i = items.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const n = (i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items[n]?.focus();
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      items[e.key === "Home" ? 0 : items.length - 1]?.focus();
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      setOpen(false);
      box.current?.querySelector<HTMLButtonElement>(".lang-btn")?.focus();
    } else if (e.key === "Tab") setOpen(false);
  };

  return (
    <div className={`lang-switch${big ? " lang-switch-big" : ""}`} ref={box}>
      <button
        type="button"
        className={`btn ${big ? "" : "btn-ghost btn-sm "}lang-btn`}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={id}
        aria-label={`${t("lang.label")}: ${cur.name}`}
        onClick={() => setOpen((v) => !v)}
      >
        <Flag code={cur.flag} />
        {!compact && <span lang={cur.code}>{cur.name}</span>}
        <span className="lang-caret" aria-hidden="true">
          ▾
        </span>
      </button>
      {open && (
        <ul className="lang-menu" id={id} ref={list} onKeyDown={onListKey} aria-label={t("lang.label")}>
          {UI_LANGUAGES.map((l) => (
            <li key={l.code}>
              <button type="button" aria-current={l.code === lang ? "true" : undefined} onClick={() => pick(l.code)} lang={l.code}>
                <Flag code={l.flag} />
                <span>{l.name}</span>
                {l.code === lang && (
                  <span className="lang-check" aria-hidden="true">
                    ✓
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { Icon } from "./components/Icons";

interface Toast {
  id: number;
  kind: "ok" | "err" | "info";
  text: string;
  hint?: string | null;
  action?: { label: string; run: () => void };
}

const Ctx = createContext<(t: Omit<Toast, "id">) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((ts) => [...ts.slice(-3), { ...t, id }]);
    window.setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), t.kind === "err" ? 9000 : 4500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <Icon name={t.kind === "err" ? "alert" : "check"} className="icon" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div>{t.text}</div>
              {t.hint && <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>{t.hint}</div>}
            </div>
            {t.action && (
              <button className="btn btn-sm btn-ghost" onClick={t.action.run}>
                {t.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);

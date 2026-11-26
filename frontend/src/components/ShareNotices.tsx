// 1.2.68: one toast per clip per platform when sharing ends: "Shared to YouTube ✓" with the link,
// "Uploaded as private" with the YouTube Studio button, or what went wrong. The same notices
// become Windows notifications through the tray (backend: web/shareevents.py).
import { useEffect, useRef } from "react";
import { req } from "../api";
import { useI18n } from "../i18n";
import { shareChanged } from "../share";
import { useToast } from "../toast";

interface Notice {
  id: number;
  kind: string;
  title: string;
  body: string;
  url: string | null;
  at: number;
}

const KINDS = ["shared", "private", "manual_ready", "share_failed", "assist_ready", "assist_action", "assist_confirm"];

export function ShareNotices() {
  const { t } = useI18n();
  const toast = useToast();
  const seen = useRef<{ boot: string | null; last: number }>({ boot: null, last: 0 });
  useEffect(() => {
    let alive = true;
    const poll = () =>
      req<{ boot: string; items: Notice[]; last: number }>("GET", `/api/notices?after=${seen.current.last}`)
        .then((d) => {
          if (!alive) return;
          if (d.boot !== seen.current.boot) {
            const first = seen.current.boot === null;
            seen.current = { boot: d.boot, last: first ? d.last : 0 };
            if (first) return; // only what happens from now on
          }
          let changed = false;
          for (const n of d.items) {
            seen.current.last = Math.max(seen.current.last, n.id);
            if (!KINDS.includes(n.kind)) continue;
            changed = true;
            const url = n.url;
            toast({
              kind: n.kind === "share_failed" ? "err" : n.kind === "private" || n.kind.startsWith("assist_") ? "info" : "ok",
              text: n.title,
              hint: n.body,
              ms: n.kind === "share_failed" || n.kind === "private" ? 15000 : 7000,
              action: url
                ? {
                    label: n.kind === "private" ? t("notice.open_studio") : t("notice.open_post"),
                    run: () => window.open(url, "_blank", "noopener"),
                  }
                : undefined,
            });
          }
          if (changed) shareChanged();
        })
        .catch(() => {});
    poll();
    const iv = window.setInterval(() => document.visibilityState === "visible" && poll(), 4000);
    return () => {
      alive = false;
      window.clearInterval(iv);
    };
  }, [t, toast]);
  return null;
}

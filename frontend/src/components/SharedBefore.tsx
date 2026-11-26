// "You already used this video" (1.2.68 on the Share page; 1.2.69 also right after a video is
// dropped or picked for import, in Easy and Pro, before any clip exists).
import { useEffect, useState } from "react";
import { useI18n } from "../i18n";
import { TARGET_NAME, type Target } from "../multipost";
import { href } from "../router";
import { shareApi, type HistorySummary } from "../share";
import { fingerprintFile } from "../fingerprint";
import { Icon } from "./Icons";

const ORDER: Target[] = ["youtube", "reels", "tiktok"];

export function AlreadyShared({ h }: { h: HistorySummary }) {
  const { t, lang, num } = useI18n();
  const date = h.first_at ? new Date(h.first_at).toLocaleDateString(`${lang}-u-nu-latn`, { day: "numeric", month: "long", year: "numeric" }) : "";
  const parts = ORDER.filter((p) => h.by_platform[p]).map((p) => t("share.before_on", { n: num(h.by_platform[p] ?? 0), name: TARGET_NAME[p] }));
  return (
    <div className="notice notice-warn share-before" role="alert">
      <Icon name="alert" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="notice-title">{t("share.before_title")}</div>
        <div>{t("share.before_body", { date, where: parts.join(", ") })}</div>
      </div>
      <a className="btn" href={href.history}>
        <Icon name="clock" /> {t("history.open")}
      </a>
    </div>
  );
}

/** What was shared before from the video being imported: a dropped / picked file (hashed here,
 *  3 MiB read) or a local path typed into the box (hashed by the server). URLs: nothing. */
export function useSharedBefore(file: File | null | undefined, path?: string): HistorySummary | null {
  const [h, setH] = useState<HistorySummary | null>(null);
  const p = (path ?? "").trim();
  const isPath = !file && p.length > 3 && !/^https?:\/\//i.test(p);
  useEffect(() => {
    setH(null);
    let off = false;
    if (file) {
      fingerprintFile(file)
        .then((fp) => shareApi.sourceHistory(fp))
        .then((r) => !off && setH(r.before))
        .catch(() => {});
    } else if (isPath) {
      const id = window.setTimeout(() => {
        shareApi
          .pathHistory(p)
          .then((r) => !off && setH(r.before))
          .catch(() => {});
      }, 400);
      return () => {
        off = true;
        window.clearTimeout(id);
      };
    }
    return () => {
      off = true;
    };
  }, [file, isPath, p]);
  return h;
}

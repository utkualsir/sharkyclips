// 1.2.74: "Send feedback / Report a bug". Opens a pre-filled GitHub issue form in a new tab.
// Filled in: the app version and a short system label from the server (/api/meta "system"), and
// for an error the message the person saw, scrubbed of paths, e-mail addresses, links and long ids.
// Nothing else (no logs, no settings, no file names), and nothing is sent until the person submits
// the form on GitHub. backend/sharkyclips/feedback.py, .github/ISSUE_TEMPLATE/*.yml (field ids).
// No imports: test_feedback.py runs this file directly in Node.

export const REPO_URL = "https://github.com/utkualsir/sharkyclips";

let info: { version: string; system: string } = { version: "", system: "" };

/** MetaProvider calls this once /api/meta is loaded (the server's version + system label). */
export function setFeedbackInfo(meta: { version?: string; system?: string } | null): void {
  if (!meta) return;
  info = { version: meta.version || "", system: meta.system || "" };
}

function browserSystem(): string {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  if (/Windows NT 10/.test(ua)) return "Windows 10 or 11";
  if (/Windows/.test(ua)) return "Windows";
  if (/Mac OS X/.test(ua)) return "macOS";
  if (/Linux/.test(ua)) return "Linux";
  return "";
}

/** Removes what could identify a person from an error text (it stays editable on GitHub anyway). */
export function scrub(text: string): string {
  return String(text || "")
    .replace(/https?:\/\/[^\s"'<>)]+/gi, (u) => {
      try {
        const x = new URL(u);
        return x.hostname === "127.0.0.1" || x.hostname === "localhost" ? "<local address>" : `${x.origin}/…`;
      } catch {
        return "<link>";
      }
    })
    .replace(/\b[A-Za-z]:[\\/][^\s"'<>|]*/g, "<path>")
    .replace(/\\\\[^\s"'<>|]+/g, "<path>")
    .replace(/(^|[\s"'(=])~?\/(?:Users|home|mnt|media|private|var|tmp|Volumes)\/[^\s"'<>)]*/g, "$1<path>")
    .replace(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, "<email>")
    .replace(/\b[A-Za-z0-9_\-]{28,}\b/g, "<id>")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 600);
}

export type FeedbackKind = "bug" | "idea";

export function feedbackUrl(kind: FeedbackKind, error?: string | null): string {
  const p = new URLSearchParams();
  if (kind === "idea") {
    p.set("template", "feature_request.yml");
    p.set("labels", "enhancement");
    p.set("source", "app");
    return `${REPO_URL}/issues/new?${p.toString()}`;
  }
  p.set("template", "bug_report.yml");
  p.set("labels", "bug");
  if (info.version) p.set("version", info.version);
  p.set("os", info.system || browserSystem());
  p.set("source", "app");
  const msg = error ? scrub(error) : "";
  if (msg) {
    p.set("title", `Error: ${msg.slice(0, 80)}`);
    p.set("what", `The app showed this error:\n\n> ${msg}\n\nWhat I was doing when it happened:\n\n`);
  }
  return `${REPO_URL}/issues/new?${p.toString()}`;
}

/** Opens the form in a new tab (must run inside the click, or the browser blocks the tab). */
export function openFeedback(kind: FeedbackKind, error?: string | null): void {
  window.open(feedbackUrl(kind, error), "_blank", "noopener,noreferrer");
}

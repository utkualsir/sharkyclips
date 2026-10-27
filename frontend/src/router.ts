import { useEffect, useState } from "react";

// Hash routes: works from any server path and survives reloads without server config.
export type StudioTab = "music" | "brand" | "words";
export type Route =
  | { name: "library" }
  | { name: "project"; id: string }
  | { name: "bestof"; id: string }
  | { name: "game"; id: string }
  | { name: "stories"; id: string }
  | { name: "settings" }
  | { name: "studio"; tab: StudioTab }
  | { name: "queue" }
  | { name: "stats" };

function parse(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  const [a, b, c] = h.split("/");
  if (a === "p" && b && c === "bestof") return { name: "bestof", id: decodeURIComponent(b) };
  if (a === "p" && b && c === "game") return { name: "game", id: decodeURIComponent(b) };
  if (a === "p" && b && c === "stories") return { name: "stories", id: decodeURIComponent(b) };
  if (a === "p" && b) return { name: "project", id: decodeURIComponent(b) };
  if (a === "settings") return { name: "settings" };
  if (a === "studio") return { name: "studio", tab: b === "brand" || b === "words" ? b : "music" };
  if (a === "queue") return { name: "queue" };
  if (a === "stats") return { name: "stats" };
  return { name: "library" };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => {
      setRoute(parse());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export const href = {
  library: "#/",
  settings: "#/settings",
  studio: (tab: StudioTab = "music") => `#/studio/${tab}`,
  queue: "#/queue",
  stats: "#/stats",
  project: (id: string) => `#/p/${encodeURIComponent(id)}`,
  bestof: (id: string) => `#/p/${encodeURIComponent(id)}/bestof`,
  game: (id: string) => `#/p/${encodeURIComponent(id)}/game`,
  stories: (id: string) => `#/p/${encodeURIComponent(id)}/stories`,
};

export function go(to: string) {
  window.location.hash = to.replace(/^#/, "");
}

import { useEffect, useState } from "react";

// Hash routes: works from any server path and survives reloads without server config.
export type Route = { name: "library" } | { name: "project"; id: string } | { name: "settings" };

function parse(): Route {
  const h = window.location.hash.replace(/^#\/?/, "");
  const [a, b] = h.split("/");
  if (a === "p" && b) return { name: "project", id: decodeURIComponent(b) };
  if (a === "settings") return { name: "settings" };
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
  project: (id: string) => `#/p/${encodeURIComponent(id)}`,
};

export function go(to: string) {
  window.location.hash = to.replace(/^#/, "");
}

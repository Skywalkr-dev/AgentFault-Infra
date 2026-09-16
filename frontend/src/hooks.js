import { useEffect, useState } from "react";

function parseHash() {
  const h = window.location.hash.slice(1) || "/";
  const [path, qs] = h.split("?");
  const params = new URLSearchParams(qs || "");
  if (path.startsWith("/t/")) {
    return { name: "detail", id: decodeURIComponent(path.slice(3)), params };
  }
  return { name: "list", params };
}

export function useRoute() {
  const [route, setRoute] = useState(parseHash);
  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return route;
}

export function navigate(to, extra) {
  if (typeof to === "string") {
    window.location.hash = to;
    return;
  }
  const { name, id, params } = to;
  if (name === "detail") {
    window.location.hash = `/t/${encodeURIComponent(id)}`;
  } else {
    const qs = new URLSearchParams(params).toString();
    window.location.hash = qs ? `/?${qs}` : "/";
  }
}

export function listRoute(params) {
  return { name: "list", params };
}
import { useEffect, useState } from "react";
import { useStore } from "./data/store.jsx";
import { apiEnabled, fetchReplay, normalizeComparison } from "./lib/api.js";

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

// Replay-comparison data for a trajectory: starts from the bundled replay
// index (works with no backend), and upgrades to the live dashboard API when
// VITE_API_BASE is configured. The DetailView is remounted per id (key={id}),
// so the initializer always sees the right id.
export function useReplayComparison(id) {
  const { replayIndex } = useStore();
  const bundled = (id && replayIndex.get(id)) || null;

  const [state, setState] = useState(() => ({
    data: bundled,
    source: bundled ? "bundle" : null,
    loading: apiEnabled,
    error: null,
  }));

  useEffect(() => {
    let alive = true;
    if (!id || !apiEnabled) return;

    fetchReplay(id)
      .then((comparison) => {
        if (!alive) return;
        setState({
          data: normalizeComparison(comparison),
          source: "api",
          loading: false,
          error: null,
        });
      })
      .catch((err) => {
        if (!alive) return;
        setState((prev) => ({
          ...prev,
          loading: false,
          error: String(err?.message ?? err),
        }));
      });

    return () => {
      alive = false;
    };
  }, [id]);

  return state;
}
// Thin client for the dashboard API (dashboard/api.py).
//
// The console works fully offline against the bundled replay index; when
// VITE_API_BASE is set it prefers the live API for replay-comparison and
// propagation-chain views and falls back to the bundle on failure.

const raw = (import.meta.env.VITE_API_BASE || "").replace(/\/+$/, "");

export const apiBase = raw;
export const apiEnabled = raw.length > 0;

const clip = (s, n = 150) =>
  typeof s === "string" && s.length > n ? s.slice(0, n - 1) + "…" : s;

async function get(path) {
  if (!apiEnabled) throw new Error("dashboard API not configured");
  const res = await fetch(`${apiBase}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const fetchReplay = (id) =>
  get(`/api/replay/${encodeURIComponent(id)}`);

export const fetchPropagation = (id) =>
  get(`/api/propagation/${encodeURIComponent(id)}`);

export const fetchMeta = () => get("/api/meta");

// --- normalizers: API speaks snake_case, the bundle speaks camelCase ---------
export function normalizeComparison(c) {
  const p = c.propagation ?? {};

  return {
    baselineId: c.baseline_id,
    faultType: c.fault_type,
    baselineScore: c.baseline_score,
    injectedScore: c.injected_score,
    successDelta: c.success_delta,
    deterministic: {
      baseline: Boolean(c.baseline_replay_deterministic),
      injected: Boolean(c.injected_replay_deterministic),
    },
    failedChecks: (c.injected_checks ?? [])
      .filter((x) => !x.passed)
      .map((x) => ({
        name: x.name,
        weight: x.weight,
        reason: clip(x.reason, 200),
        steps: x.steps ?? [],
      })),
    checks: (c.injected_checks ?? []).map((x) => ({
      name: x.name,
      passed: Boolean(x.passed),
      weight: x.weight,
    })),
    propagation: {
      originStep: p.origin_step ?? null,
      faultType: p.fault_type ?? c.fault_type ?? null,
      affectedSteps: p.affected_steps ?? [],
      edges: p.edges ?? [],
      outcome: p.outcome ?? null,
      nodes: (p.nodes ?? []).map((n) => ({
        stepIndex: n.step_index,
        stepType: n.step_type,
        agent: n.agent,
        status: n.status,
        isOrigin: Boolean(n.is_origin),
        isRootCause: Boolean(n.is_root_cause),
        changes: (n.changes ?? []).map((ch) => ({
          field: ch.field,
          before: clip(ch.before),
          after: clip(ch.after),
        })),
      })),
    },
  };
}

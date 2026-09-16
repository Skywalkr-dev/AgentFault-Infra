// AgentFault Console — build-time data aggregator.
//
// This script READS the real dataset (../data/trajectories/...) and emits a
// normalized set of static JSON assets into public/data/ that the browser can
// consume. It never writes back to the dataset and the original files are
// left byte-for-byte untouched.
//
// Assets produced:
//   public/data/baseline.json   — normalized baseline trajectories
//   public/data/injected.json   — normalized fault-injected trajectories
//   public/data/meta.json       — dataset summary + fault taxonomy + demo pick

import { readdirSync, readFileSync, writeFileSync, mkdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DATA_DIR = join(ROOT, "..", "data", "trajectories");
const BASELINE_DIR = join(DATA_DIR, "baseline");
const INJECTED_DIR = join(DATA_DIR, "injected");
const OUT_DIR = join(ROOT, "public", "data");

const STEP_TYPE_MAP = {
  retrieval: "RETRIEVAL",
  llm_call: "LLM_CALL",
  tool_call: "TOOL_CALL",
  tool_result: "TOOL_RESULT",
};

// ---------------------------------------------------------------------------
// Taxonomy (the 20 defined fault types + their groups). `represented` is
// derived from the real data below, never fabricated.
// ---------------------------------------------------------------------------
const FAULT_GROUPS = [
  { id: "PLAN", label: "Plan", prefix: "PLAN_" },
  { id: "TOOL", label: "Tool", prefix: "TOOL_" },
  { id: "KNOWLEDGE", label: "Knowledge", prefix: "KNOW_" },
  { id: "MULTI-AGENT", label: "Multi-agent", prefix: "MA_" },
  { id: "CONTROL", label: "Control", prefix: "CTRL_" },
  { id: "SECURITY", label: "Security", prefix: "SEC_" },
];

const FAULT_TAXONOMY = [
  "PLAN_MISSING_STEP",
  "PLAN_INCORRECT_SUCCESS_CRITERIA",
  "PLAN_INVALID_DEPENDENCY",
  "TOOL_WRONG_TOOL",
  "TOOL_WRONG_ARGUMENT",
  "TOOL_UNNECESSARY_CALL",
  "TOOL_FAILED_RECOVERY",
  "KNOW_RETRIEVAL_FAILURE",
  "KNOW_CITATION_MISMATCH",
  "KNOW_CONTEXT_TRUNCATION",
  "MA_INCORRECT_HANDOFF",
  "MA_INFORMATION_LOSS",
  "MA_MISSING_RESPONSIBILITY",
  "MA_ROLE_OVERLAP",
  "CTRL_LOOP",
  "CTRL_PREMATURE_TERMINATION",
  "CTRL_EXCESSIVE_EXPLORATION",
  "SEC_PROMPT_INJECTION",
  "SEC_UNAUTHORIZED_ACTION",
  "SEC_CROSS_USER_DATA_LEAKAGE",
].map((type) => {
  const group = FAULT_GROUPS.find((g) => type.startsWith(g.prefix))?.id ?? "PLAN";
  return { type, group };
});

const faultGroup = (type) =>
  FAULT_TAXONOMY.find((t) => t.type === type)?.group ?? "PLAN";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
function safeParseJsonl(text, id) {
  const events = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    try {
      events.push(JSON.parse(line));
    } catch (err) {
      console.warn(`[warn] ${id}: skipping unparseable line ${i + 1} (${err.message})`);
    }
  }
  return events;
}

function toPrimitiveString(v, max = 160) {
  if (v === undefined || v === null) return String(v);
  if (typeof v === "string") {
    const s = v.replace(/\s+/g, " ").trim();
    return s.length > max ? s.slice(0, max) + "…" : s;
  }
  const s = JSON.stringify(v);
  return s.length > max ? s.slice(0, max) + "…" : s;
}

function extractTask(eventsOrSteps, prefer) {
  if (prefer && typeof prefer === "string" && prefer.trim()) return prefer.trim();
  for (const e of eventsOrSteps) {
    if (e && e.input && typeof e.input === "string" && e.input.trim()) {
      return e.input.trim();
    }
    if (e && e.input && typeof e.input === "object") {
      const q = e.input.query ?? e.input.query_text ?? e.input.task;
      if (typeof q === "string" && q.trim()) return q.trim();
    }
  }
  return "";
}

function uniqueAgents(steps) {
  const s = new Set();
  for (const st of steps) if (st.agent) s.add(st.agent);
  return [...s].sort();
}

function outcomeFromStatus(status, note) {
  const ok = status === "success" || status === "SUCCESS";
  return {
    status: ok ? "SUCCESS" : "FAIL",
    successScore: ok ? 1 : 0,
    note: note || undefined,
  };
}

// ---------------------------------------------------------------------------
// Baseline loaders (two on-disk shapes: .jsonl lines and .json event arrays)
// ---------------------------------------------------------------------------
function normalizeBaselineEvent(e, id) {
  const type = STEP_TYPE_MAP[e.event_type];
  if (!type) return null;
  return {
    index: e.step,
    type,
    agent: e.agent ?? null,
    tool: e.tool ?? null,
    status: e.status ?? "success",
    input: e.input ?? null,
    output: e.output ?? null,
    docs: e.retrieved_docs ?? null,
    metadata: e.metadata && typeof e.metadata === "object" ? e.metadata : {},
    isRootCause: false,
  };
}

function loadBaselineFile(file) {
  const id = file.name.replace(/\.(jsonl|json)$/i, "");
  const raw = readFileSync(file.path, "utf8");
  let events;

  if (/\.jsonl$/i.test(file.name)) {
    events = safeParseJsonl(raw, file.name);
  } else {
    try {
      const parsed = JSON.parse(raw);
      events = Array.isArray(parsed) ? parsed : parsed.events ?? [];
    } catch {
      events = safeParseJsonl(raw, file.name);
    }
  }

  const start = events.find((e) => e.event_type === "trajectory_start");
  const end = events.find((e) => e.event_type === "trajectory_end");
  const meta = end?.metadata ?? {};

  const beforeSteps = events.map((e) => normalizeBaselineEvent(e, file.name)).filter(Boolean);
  const steps = beforeSteps.map((st, i) => ({ ...st, index: i + 1 }));

  return {
    id,
    source: "BASELINE",
    baseId: null,
    task:
      extractTask(events, start?.input?.query) ??
      extractTask(events),
    config: {
      framework: null,
      model: null,
      temperature: null,
      agents: uniqueAgents(steps),
    },
    outcome: outcomeFromStatus(end?.status ?? "success", end?.output),
    numSteps: steps.length,
    agents: uniqueAgents(steps),
    stepTypes: steps.map((s) => s.type),
    steps,
    variantCount: 0,
    variantFaults: [],
  };
}

// ---------------------------------------------------------------------------
// Injected loaders (.json AgentFaultRecord + one legacy .jsonl)
// ---------------------------------------------------------------------------
function normInjectedStep(s) {
  return {
    index: s.step_index ?? s.step,
    type: s.step_type ?? STEP_TYPE_MAP[s.event_type],
    agent: s.agent_id ?? s.agent ?? null,
    tool: s.tool_name ?? s.tool ?? null,
    status: s.status ?? "success",
    input: s.input ?? null,
    output: s.output ?? null,
    docs: s.retrieved_docs ?? null,
    metadata: s.metadata && typeof s.metadata === "object" ? s.metadata : {},
    isRootCause: Boolean(s.is_root_cause),
  };
}

function loadInjectedJson(file) {
  let rec;
  try {
    rec = JSON.parse(readFileSync(file.path, "utf8"));
  } catch {
    return null;
  }
  const steps = (rec.steps ?? []).map(normInjectedStep).filter((s) => s.type);
  const faultType = rec.fault_type ?? null;
  const originStep = rec.origin_step ?? null;
  const params = rec.injection_params ?? {};

  return {
    id: rec.trajectory_id,
    source: "INJECTED",
    split: rec.split ?? null,
    baseId: (rec.trajectory_id ?? "").split("_fault_")[0],
    task:
      extractTask(steps) ||
      toPrimitiveString(rec.task_id).replace(/^\{|\}$/g, ""),
    config: {
      framework: rec.agent_config?.framework ?? null,
      model: rec.agent_config?.model ?? null,
      temperature: rec.agent_config?.temperature ?? null,
      agents: rec.agent_config?.agents_involved ?? steps.map((s) => s.agent).filter(Boolean),
    },
    outcome: {
      status: rec.outcome?.status ?? "FAIL",
      successScore: rec.outcome?.success_score ?? 0,
    },
    fault: faultType
      ? {
          type: faultType,
          group: faultGroup(faultType),
          originStep,
          operator: params.operator ?? null,
          seed: params.random_seed ?? null,
          params,
        }
      : null,
    numSteps: steps.length,
    agents: uniqueAgents(steps),
    stepTypes: steps.map((s) => s.type),
    steps,
  };
}

function loadInjectedLegacyJsonl(file) {
  // traj_XXXX_INJECTED_FAULT_TYPE_N.jsonl — event stream with fault metadata
  // carried on the injected step event.
  const raw = safeParseJsonl(readFileSync(file.path, "utf8"), file.name);
  const id = file.name.replace(/\.jsonl$/i, "");
  const m = id.match(/^(traj_[0-9a-f]+)_INJECTED_(.+)_(\d+)$/);
  const faultType = m?.[2] ?? null;
  const originStepRaw = m?.[3] ? Number(m[3]) : null;

  let injectedStep = null;
  for (const e of raw) {
    if (e.metadata?.is_root_cause) injectedStep = e;
  }

  const faultInfo = normalizeBaselineEvent(injectedStep, file.name);
  const steps = raw
    .map(normalizeBaselineEvent)
    .filter(Boolean)
    .map((s, i) => ({ ...s, index: i + 1 }));

  const actualFaultType =
    injectedStep?.metadata?.fault_type ||
    faultType ||
    "TOOL_WRONG_ARGUMENT";

  const rawOrig = injectedStep?.metadata?.original_input ?? null;
  const rawInj = injectedStep?.metadata?.injected_input ?? null;
  const argName =
    rawOrig && rawInj && typeof rawOrig === "object" && typeof rawInj === "object"
      ? Object.keys(rawInj).find((k) => rawInj[k] !== rawOrig[k]) || null
      : null;

  const start = raw.find((e) => e.event_type === "trajectory_start");
  const end = raw.find((e) => e.event_type === "trajectory_end");

  return {
    id,
    source: "INJECTED",
    baseId: id.split("_INJECTED_")[0],
    task: extractTask(steps, start?.input?.query),
    config: {
      framework: null,
      model: null,
      temperature: null,
      agents: uniqueAgents(steps),
    },
    outcome: outcomeFromStatus(end?.status ?? "error", null),
    fault: actualFaultType
      ? {
          type: actualFaultType,
          group: faultGroup(actualFaultType),
          originStep: faultInfo?.index ?? originStepRaw ?? null,
          operator: "REPLACE_ARGUMENT_VALUE",
          seed: injectedStep?.metadata?.random_seed ?? null,
          params: {
            operator: "REPLACE_ARGUMENT_VALUE",
            argument_name: argName,
            original_value: argName ? rawOrig?.[argName] : rawOrig,
            injected_value: argName ? rawInj?.[argName] : rawInj,
            original_input: rawOrig,
            injected_input: rawInj,
          },
        }
      : null,
    numSteps: steps.length,
    agents: uniqueAgents(steps),
    stepTypes: steps.map((s) => s.type),
    steps: steps.map((s, _) => ({
      ...s,
      isRootCause: s.isRootCause || s.index === faultInfo?.index,
    })),
  };
}

// ---------------------------------------------------------------------------
// Build
// ---------------------------------------------------------------------------
console.log("AgentFault Console — data build");
console.log(`  reading baselines  : ${BASELINE_DIR}`);
console.log(`  reading injected   : ${INJECTED_DIR}`);

const baselineFiles = readdirSync(BASELINE_DIR)
  .map((f) => ({ name: f, path: join(BASELINE_DIR, f) }))
  .filter((f) => statSync(f.path).isFile())
  .filter((f) => /\.(jsonl|json)$/i.test(f.name));

const injectedFiles = readdirSync(INJECTED_DIR)
  .map((f) => ({ name: f, path: join(INJECTED_DIR, f) }))
  .filter((f) => statSync(f.path).isFile())
  .filter((f) => /\.(jsonl|json)$/i.test(f.name));

const baselines = baselineFiles
  .map(loadBaselineFile)
  .filter(Boolean)
  .sort((a, b) => a.id.localeCompare(b.id));

const injected = [];
for (const file of injectedFiles) {
  const rec = /\.json$/i.test(file.name)
    ? loadInjectedJson(file)
    : loadInjectedLegacyJsonl(file);
  if (rec) injected.push(rec);
}
injected.sort((a, b) => a.id.localeCompare(b.id));

// Link baseline -> injected variants.
const byBase = new Map();
for (const rec of injected) {
  if (!rec.baseId) continue;
  if (!byBase.has(rec.baseId)) byBase.set(rec.baseId, []);
  byBase.get(rec.baseId).push(rec);
}
for (const b of baselines) {
  const variants = byBase.get(b.id) ?? [];
  b.variantCount = variants.length;
  b.variantFaults = [...new Set(variants.map((v) => v.fault?.type).filter(Boolean))].sort();
  if (b.variantCount === 0) delete b.variantFaults;
}

// Numbers / taxonomy representation derived from the data.
const typeCount = new Map();
for (const rec of injected) {
  const t = rec.fault?.type;
  if (t) typeCount.set(t, (typeCount.get(t) ?? 0) + 1);
}
const represented = new Set(typeCount.keys());
const missingFaults = FAULT_TAXONOMY.filter((t) => !represented.has(t.type)).map((t) => t.type);

const faultTaxonomy = FAULT_TAXONOMY.map(({ type, group }) => ({
  type,
  group,
  represented: represented.has(type),
  count: typeCount.get(type) ?? 0,
}));

const groups = FAULT_GROUPS.map((g) => {
  const members = faultTaxonomy.filter((t) => t.group === g.id);
  return {
    ...g,
    total: members.length,
    represented: members.filter((t) => t.represented).length,
    count: members.reduce((a, t) => a + t.count, 0),
  };
});

const stepTypeCount = new Map();
for (const rec of injected) {
  for (const s of rec.steps) stepTypeCount.set(s.type, (stepTypeCount.get(s.type) ?? 0) + 1);
}
const agentSet = new Set();
for (const rec of injected) for (const a of rec.agents) agentSet.add(a);

// Demo pick: prefer an injected trajectory with an understandable TOOL fault and
// the full RETRIEVAL -> LLM_CALL -> TOOL_CALL -> LLM_CALL shape, real data only.
const DEMO_PREF = [
  "TOOL_WRONG_ARGUMENT",
  "TOOL_WRONG_TOOL",
  "TOOL_FAILED_RECOVERY",
  "SEC_PROMPT_INJECTION",
];
const demoIds = [];
{
  const scored = [];
  for (const rec of injected) {
    const seq = rec.stepTypes.join("|");
    const hasShape = seq.includes("RETRIEVAL|LLM_CALL|TOOL_CALL|LLM_CALL");
    const prefIdx = rec.fault ? DEMO_PREF.indexOf(rec.fault.type) : -1;
    if (prefIdx < 0 || !hasShape) continue;
    scored.push({ rec, prefIdx });
  }
  scored.sort((a, b) => a.prefIdx - b.prefIdx || b.rec.numSteps - a.rec.numSteps);
  for (const { rec } of scored) demoIds.push(rec.id);
}
if (demoIds.length === 0) {
  console.warn("[warn] no preferred demo candidate found; falling back to any injected record");
  demoIds.push(injected[0]?.id ?? null);
}

const meta = {
  generatedAt: new Date().toISOString(),
  counts: {
    baseline: baselines.length,
    injected: injected.length,
    baselineSteps: baselines.reduce((a, r) => a + r.numSteps, 0),
    injectedSteps: injected.reduce((a, r) => a + r.numSteps, 0),
    steps: [...baselines, ...injected].reduce((a, r) => a + r.numSteps, 0),
  },
  faultTaxonomy,
  groups,
  missingFaults,
  stepTypeCount: Object.fromEntries(stepTypeCount),
  agents: [...agentSet].sort(),
  demoIds,
};

mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(join(OUT_DIR, "baseline.json"), JSON.stringify(baselines));
writeFileSync(join(OUT_DIR, "injected.json"), JSON.stringify(injected));
writeFileSync(join(OUT_DIR, "meta.json"), JSON.stringify(meta));

console.log("  written:");
console.log(`    public/data/baseline.json  (${baselines.length} trajectories)`);
console.log(`    public/data/injected.json  (${injected.length} trajectories)`);
console.log(`    public/data/meta.json      (${meta.faultTaxonomy.length} fault types)`);
console.log(`  represented fault types: ${represented.size}/20`);
console.log(`  missing: ${missingFaults.join(", ") || "none"}`);
console.log(`  demo pick: ${demoIds[0] ?? "none"}`);

const orphans = injected.filter((r) => r.baseId && !byBase.get(r.baseId)?.some((_, i) => _));
if (orphans.length) console.warn(`[warn] ${orphans.length} injected records have no baseline match`);
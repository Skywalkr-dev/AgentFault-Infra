// Step types (normalized vocabulary used across baseline + injected records).
export const STEP_TYPES = {
  RETRIEVAL: { color: "var(--c-retrieval)", label: "Retrieval" },
  LLM_CALL: { color: "var(--c-llm)", label: "LLM call" },
  TOOL_CALL: { color: "var(--c-tool)", label: "Tool call" },
  TOOL_RESULT: { color: "var(--c-toolresult)", label: "Tool result" },
};

export const FAULT_GROUPS = {
  PLAN: { color: "var(--c-f-plan)", label: "Plan" },
  TOOL: { color: "var(--c-f-tool)", label: "Tool" },
  KNOWLEDGE: { color: "var(--c-f-know)", label: "Knowledge" },
  "MULTI-AGENT": { color: "var(--c-f-ma)", label: "Multi-agent" },
  CONTROL: { color: "var(--c-f-ctrl)", label: "Control" },
  SECURITY: { color: "var(--c-f-sec)", label: "Security" },
};

export function stepTypeInfo(type) {
  return STEP_TYPES[type] ?? { color: "var(--c-muted)", label: type };
}

export function groupInfo(id) {
  return FAULT_GROUPS[id] ?? { color: "var(--c-muted)", label: id };
}

export function humanize(value) {
  if (value == null) return "";
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function shortFault(type) {
  // TOOL_WRONG_ARGUMENT -> "Wrong argument"
  const parts = String(type).split("_");
  const first = parts[0];
  const rest = parts.slice(1);
  const known = { PLAN: "Plan", TOOL: "Tool", KNOW: "Knowledge", MA: "Multi-agent", CTRL: "Control", SEC: "Security" };
  const head = known[first] ?? humanize(first);
  return rest.length ? `${rest.join(" ").replace(/^\w/, (c) => c.toLowerCase())}` : head;
}

export const STEP_TYPE_ORDER = ["RETRIEVAL", "LLM_CALL", "TOOL_CALL", "TOOL_RESULT"];
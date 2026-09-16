export function shortText(value, max = 120) {
  if (value == null) return "";
  let s = typeof value === "string" ? value : JSON.stringify(value);
  s = s.replace(/\s+/g, " ").trim();
  if (s.length <= max) return s;
  return s.slice(0, max) + "…";
}

export function parseSize(v) {
  if (v == null) return 0;
  if (typeof v === "string") return v.length;
  try {
    return JSON.stringify(v).length;
  } catch {
    return 0;
  }
}

export function isBigValue(v, threshold = 300) {
  return parseSize(v) > threshold;
}

export function jsonPretty(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export function csv(items, max = 8) {
  if (!items || items.length === 0) return "";
  if (items.length <= max) return items.join(", ");
  return `${items.slice(0, max).join(", ")} +${items.length - max}`;
}

export function parseQuery(taskValue) {
  // Injected records may carry a Python-dict string as task_id.
  // Resolve to a readable query string when possible.
  if (typeof taskValue !== "string") return taskValue;
  const m = taskValue.match(/['"]query['"]\s*:\s*['"](.*?)['"]/);
  return m ? m[1] : taskValue;
}

export function elide(str, head = 60, tail = 40) {
  if (typeof str !== "string" || str.length <= head + tail) return str;
  return `${str.slice(0, head)}…${str.slice(-tail)}`;
}
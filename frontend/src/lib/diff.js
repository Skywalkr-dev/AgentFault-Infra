// Structural diff helpers used for baseline <-> injected comparison.

const MAX_DEPTH = 5;
const MAX_CHANGES = 60;

function isNullish(v) {
  return v === undefined || v === null;
}

export function sameValue(a, b) {
  if (isNullish(a) && isNullish(b)) return true;
  if (typeof a !== typeof b) return false;
  if (typeof a === "object") return JSON.stringify(a) === JSON.stringify(b);
  return Object.is(a, b);
}

export function diffValues(a, b, maxDepth = MAX_DEPTH, depth = 0, path = []) {
  const out = [];

  if (depth >= maxDepth) {
    if (!sameValue(a, b)) {
      out.push({ path, before: a, after: b, kind: "changed" });
    }
    return out;
  }

  // Nullish
  if (isNullish(a) || isNullish(b)) {
    if (isNullish(a) && isNullish(b)) return out;
    if (isNullish(a)) out.push({ path, before: undefined, after: b, kind: "added" });
    else if (isNullish(b)) out.push({ path, before: a, after: undefined, kind: "removed" });
    return out;
  }

  const typeA = typeof a;
  const typeB = typeof b;
  if (typeA !== typeB) {
    out.push({ path, before: a, after: b, kind: "changed" });
    return out;
  }

  if (typeA !== "object") {
    if (!sameValue(a, b)) out.push({ path, before: a, after: b, kind: "changed" });
    return out;
  }

  // Objects / arrays
  if (Array.isArray(a) && Array.isArray(b)) {
    const n = Math.max(a.length, b.length);
    for (let i = 0; i < n; i++) {
      if (i >= a.length) out.push({ path: [...path, i], before: undefined, after: b[i], kind: "added" });
      else if (i >= b.length) out.push({ path: [...path, i], before: a[i], after: undefined, kind: "removed" });
      else out.push(...diffValues(a[i], b[i], maxDepth, depth + 1, [...path, i]));
      if (out.length > MAX_CHANGES) return out;
    }
    return out;
  }

  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    const hasA = Object.prototype.hasOwnProperty.call(a, k);
    const hasB = Object.prototype.hasOwnProperty.call(b, k);
    if (!hasA && hasB) out.push({ path: [...path, k], before: undefined, after: b[k], kind: "added" });
    else if (hasA && !hasB) out.push({ path: [...path, k], before: a[k], after: undefined, kind: "removed" });
    else out.push(...diffValues(a[k], b[k], maxDepth, depth + 1, [...path, k]));
    if (out.length > MAX_CHANGES) return out;
  }
  return out;
}

// truncated-on-purpose helper: produce a compact before->after string pair
export function compactDelta(before, after) {
  const b = valueToCompactString(before);
  const a = valueToCompactString(after);
  return { before: b, after: a };
}

function valueToCompactString(v, max = 260) {
  if (isNullish(v)) return v === null ? "null" : "—";
  if (typeof v === "string") {
    const s = v.replace(/\s+/g, " ").trim();
    return s.length > max ? s.slice(0, max) + "…" : s;
  }
  const s = JSON.stringify(v);
  return s && s.length > max ? s.slice(0, max) + "…" : s ?? String(v);
}

export function valueShort(v, max = 260) {
  return valueToCompactString(v, max);
}

// ---------------------------------------------------------------------------
// Step-sequence alignment (longest common subsequence over step type)
// ---------------------------------------------------------------------------
export function alignSequences(bSteps, iSteps, key = (s) => s.type) {
  const n = bSteps.length;
  const m = iSteps.length;
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));

  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] =
        key(bSteps[i]) === key(iSteps[j])
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const pairs = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (key(bSteps[i]) === key(iSteps[j])) {
      pairs.push({ b: i, i: j });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      pairs.push({ b: i, i: null });
      i++;
    } else {
      pairs.push({ b: null, i: j });
      j++;
    }
  }
  while (i < n) {
    pairs.push({ b: i, i: null });
    i++;
  }
  while (j < m) {
    pairs.push({ b: null, i: j });
    j++;
  }
  return pairs;
}

const FIELDS = [
  { key: "agent", label: "agent" },
  { key: "tool", label: "tool" },
  { key: "status", label: "status" },
  { key: "input", label: "input" },
  { key: "output", label: "output" },
  { key: "docs", label: "docs" },
  { key: "metadata", label: "metadata" },
];

// Field-level diff between a matched baseline step and injected step.
export function stepFieldChanges(bStep, iStep) {
  const changes = [];
  for (const f of FIELDS) {
    if (f.key === "docs") {
      // Baseline events typically don't carry retrieved_docs while injected
      // records often carry an empty array — only diff when one side has
      // real documents so the comparison stays meaningful.
      const beforeHas = Array.isArray(bStep?.docs) && bStep.docs.length > 0;
      const afterHas = Array.isArray(iStep?.docs) && iStep.docs.length > 0;
      if (!beforeHas && !afterHas) continue;
    }
    for (const ch of diffValues(bStep?.[f.key], iStep?.[f.key])) {
      ch.field = f.key;
      ch.label = f.label;
      changes.push(ch);
    }
  }
  return changes;
}

export function groupChanges(changes) {
  const byField = new Map();
  for (const c of changes) {
    if (!byField.has(c.field)) byField.set(c.field, []);
    byField.get(c.field).push(c);
  }
  return byField;
}

export function countChanges(changes) {
  const count = { changed: 0, added: 0, removed: 0 };
  for (const c of changes) count[c.kind === "added" ? "added" : c.kind === "removed" ? "removed" : "changed"]++;
  return count;
}
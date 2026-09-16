import { ArrowRight, ArrowDown, Gauge, AlertTriangle, Crosshair, Dice5, GitCompareArrows } from "lucide-react";
import { Badge } from "../shared/Badge.jsx";
import { groupInfo, shortFault, stepTypeInfo } from "../../lib/taxonomy.js";
import { compactDelta } from "../../lib/diff.js";
import { isBigValue } from "../../lib/format.js";

function pickPrimaryDelta(changes) {
  const order = ["tool", "input", "output", "status", "agent", "docs", "metadata"];
  const byField = new Map();
  for (const c of changes ?? []) {
    if (c.kind === "changed") {
      if (!byField.has(c.field)) byField.set(c.field, c);
    }
  }
  for (const f of order) {
    if (!byField.has(f)) continue;
    const c = byField.get(f);
    const { before, after } = c;
    // String appended in the injected value (e.g. SEC_PROMPT_INJECTION):
    // show the appended tail rather than the two long identical prompts.
    if (typeof before === "string" && typeof after === "string" && after.startsWith(before)) {
      const tail = after.slice(before.length).trim();
      if (tail) {
        return { field: f, before: `…${before.slice(-70).trim()}`, after: tail, appended: true };
      }
    }
    return { field: f, ...compactDelta(before, after) };
  }
  return null;
}

export function FaultCard({ fault, baselineStep, injectedStep, changes }) {
  if (!fault) return null;
  const info = groupInfo(fault.group);
  const stage = baselineStep ? baselineStep : injectedStep;
  const delta = pickPrimaryDelta(changes);
  const fieldColor = { tool: "var(--c-tool)", input: "var(--c-llm)", output: "var(--c-toolresult)", status: "var(--c-red)", agent: "var(--c-ma2)", docs: "var(--c-retrieval)", metadata: "var(--c-muted)" };
  const color = fieldColor[delta?.field] ?? "var(--c-amber)";

  return (
    <section className="faultcard" style={{ "--fc": info.color }}>
      <header className="faultcard__head">
        <span className="faultcard__title">
          <GitCompareArrows size={15} />
          Fault injection
        </span>
        <span className="faultcard__headmeta">
          <Badge tone="amber">{shortFault(fault.type)}</Badge>
          <Badge tone="slate">{fault.type}</Badge>
        </span>
      </header>

      <div className="faultcard__stage">
        <div className="faultcard__node faultcard__node--orig">
          <div className="faultcard__node-label">
            <span className="faultcard__node-dot" style={{ "--d": "var(--c-green)" }} />
            Baseline
          </div>
          <div className="faultcard__node-card">
            <div className="faultcard__node-title">
              STEP {stage?.index ?? "?"} · {stage ? stepTypeInfo(stage.type).label.toUpperCase() : "—"}
            </div>
            {stage?.agent && <div className="faultcard__node-sub">agent · {stage.agent}</div>}
            {stage?.tool && <div className="faultcard__node-sub">tool · {stage.tool}</div>}
            {delta && (
              <div className="faultcard__value" style={{ "--vc": color }}>
                <span className="faultcard__value-key">
                  {delta.field}
                  {delta.appended && <em className="faultcard__appended">· appended</em>}
                </span>
                <pre className="faultcard__value-pre">{delta.before}</pre>
              </div>
            )}
          </div>
        </div>

        <div className="faultcard__flow">
          <div className="faultcard__operator" title="Fault operator applied to this step">
            <span className="faultcard__operator-icon">
              <ArrowDown size={13} />
              <ArrowRight size={13} />
            </span>
            <span className="faultcard__operator-name">{fault.operator ?? "MUTATE_STEP"}</span>
          </div>
          <div className="faultcard__arrow faultcard__arrow--a" aria-hidden>
            <ArrowRight size={16} />
          </div>
          <div className="faultcard__arrow faultcard__arrow--b" aria-hidden>
            <ArrowRight size={16} />
          </div>
        </div>

        <div className="faultcard__node faultcard__node--inj">
          <div className="faultcard__node-label">
            <span className="faultcard__node-dot" style={{ "--d": "var(--c-red)" }} />
            Injected
          </div>
          <div className="faultcard__node-card faultcard__node-card--root">
            <div className="faultcard__node-title">
              STEP {injectedStep?.index ?? "?"} · {injectedStep ? stepTypeInfo(injectedStep.type).label.toUpperCase() : "—"}
            </div>
            {injectedStep?.agent && <div className="faultcard__node-sub">agent · {injectedStep.agent}</div>}
            {injectedStep?.tool && <div className="faultcard__node-sub">tool · {injectedStep.tool}</div>}
            {delta && (
              <div className="faultcard__value" style={{ "--vc": color }}>
                <span className="faultcard__value-key">
                  {delta.field}
                  {delta.appended && <em className="faultcard__appended">· appended</em>}
                </span>
                <pre className="faultcard__value-pre">{delta.after}</pre>
              </div>
            )}
            <div className="faultcard__rootbadge">
              <Crosshair size={11} /> ROOT CAUSE
            </div>
          </div>
        </div>
      </div>

      <div className="faultcard__meta">
        <div className="faultcard__row">
          <span>
            <AlertTriangle size={12} /> type
          </span>
          <strong>{fault.type}</strong>
        </div>
        <div className="faultcard__row">
          <span>
            <Gauge size={12} /> origin step
          </span>
          <strong>#{fault.originStep ?? "—"}</strong>
        </div>
        <div className="faultcard__row">
          <span>
            <GitCompareArrows size={12} /> operator
          </span>
          <strong>{fault.operator ?? "—"}</strong>
        </div>
        <div className="faultcard__row">
          <span>
            <Dice5 size={12} /> seed
          </span>
          <strong className="mono">{fault.seed ?? "—"}</strong>
        </div>
        <div className="faultcard__row">
          <span>outcome</span>
          <strong className="text--fail">FAIL</strong>
        </div>
        <div className="faultcard__row">
          <span>root cause</span>
          <strong>step {fault.originStep ?? "?"}</strong>
        </div>
      </div>
    </section>
  );
}
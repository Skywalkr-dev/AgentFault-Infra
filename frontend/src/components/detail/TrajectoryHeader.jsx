import { ArrowLeft, Copy, Check, GitBranch, Gauge } from "lucide-react";
import { useState } from "react";
import { Badge } from "../shared/Badge.jsx";
import { StepChips } from "../shared/StepChips.jsx";
import { groupInfo, shortFault } from "../../lib/taxonomy.js";
import { navigate } from "../../hooks.js";

function MetaItem({ k, v, mono }) {
  return (
    <div className="meta">
      <span className="meta__k">{k}</span>
      <span className={`meta__v ${mono ? "meta__v--mono" : ""}`}>{v || "—"}</span>
    </div>
  );
}

export function TrajectoryHeader({ rec, baseline }) {
  const [copied, setCopied] = useState(false);
  const inj = rec.source === "INJECTED";
  const groupColor = inj && rec.fault ? groupInfo(rec.fault.group).color : null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(rec.id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <section className={`thead ${inj ? "thead--inj" : "thead--base"}`}>
      <button className="thead__back" onClick={() => navigate("/")} title="Back to trajectories">
        <ArrowLeft size={15} />
      </button>

      <div className="thead__main">
        <div className="thead__idrow">
          <h1 className="thead__id" title={rec.id}>
            {rec.id}
          </h1>
          <button className="btn-icon" onClick={copy} title="Copy trajectory id">
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
          <div className="thead__badges">
            <Badge tone={inj ? "amber" : "cyan"}>{inj ? "INJECTED" : "NATURAL"}</Badge>
            <Badge tone={rec.outcome.status === "FAIL" ? "red" : "green"}>
              {rec.outcome.status === "FAIL" ? "FAIL" : "SUCCESS"}
            </Badge>
            {inj && rec.fault && (
              <Badge tone="slate" className="groupedge" style={{ "--gc": groupColor }}>
                <span className="inline-dot" style={{ "--gc": groupColor }} />
                {groupInfo(rec.fault.group).label} · {shortFault(rec.fault.type)}
              </Badge>
            )}
            {rec.fault?.operator && <Badge tone="violet">{rec.fault.operator}</Badge>}
            {rec.split && <Badge tone="slate">{rec.split}</Badge>}
          </div>
        </div>

        {rec.task && <p className="thead__task">“{rec.task}”</p>}

        {baseline && (
          <div className="thead__pair">
            <GitBranch size={13} />
            <span>derived from</span>
            <button
              className="link"
              onClick={() => navigate({ name: "detail", id: baseline.id })}
              title={baseline.task}
            >
              {baseline.id}
            </button>
          </div>
        )}
      </div>

      <div className="thead__side">
        <div className="thead__steps">
          <div className="thead__steps-label">
            <Gauge size={13} /> execution path
          </div>
          <StepChips steps={rec.stepTypes} size="md" />
        </div>
        <div className="thead__meta-grid">
          <MetaItem k="steps" v={`${rec.numSteps}`} mono />
          <MetaItem k="agents" v={rec.agents.length ? rec.agents.join(", ") : "—"} />
          <MetaItem k="framework" v={rec.config?.framework ?? "—"} />
          <MetaItem k="model" v={rec.config?.model ?? "—"} mono />
          <MetaItem k="temperature" v={rec.config?.temperature != null ? `${rec.config.temperature}` : "—"} mono />
          <MetaItem k="status" v={rec.outcome.status} />
          <MetaItem k="score" v={`${rec.outcome.successScore}`} mono />
          {inj && rec.fault?.originStep != null && <MetaItem k="origin step" v={`${rec.fault.originStep}`} mono />}
          {rec.source === "BASELINE" && rec.variantCount > 0 && (
            <MetaItem k="variants" v={`${rec.variantCount} injected`} />
          )}
        </div>
      </div>
    </section>
  );
}
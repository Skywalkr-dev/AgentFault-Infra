import { ArrowRight, Layers, Zap, Users } from "lucide-react";
import { Badge } from "../shared/Badge.jsx";
import { StepChips } from "../shared/StepChips.jsx";
import { groupInfo, shortFault } from "../../lib/taxonomy.js";
import { navigate } from "../../hooks.js";

export function TrajectoryCard({ rec, baseline }) {
  const injected = rec.source === "INJECTED";
  const group = injected && rec.fault ? groupInfo(rec.fault.group).color : null;

  return (
    <article
      className={`trajcard ${injected ? "trajcard--inj" : "trajcard--base"} ${baseline ? "has-baseline" : ""}`}
      onClick={() => navigate({ name: "detail", id: rec.id })}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          navigate({ name: "detail", id: rec.id });
        }
      }}
    >
      <div className="trajcard__main">
        <div className="trajcard__top">
          <span className="trajcard__id">{rec.id}</span>
          <span className="trajcard__badges">
            <Badge tone={injected ? "amber" : "cyan"}>{injected ? "INJECTED" : "NATURAL"}</Badge>
            <Badge tone={rec.outcome.status === "FAIL" ? "red" : "green"}>
              {rec.outcome.status === "FAIL" ? "FAIL" : "SUCCESS"}
            </Badge>
            {injected && rec.fault && (
              <Badge tone="slate" className="trajcard__fault" title={rec.fault.type}>
                <span className="inline-dot" style={{ "--gc": group }} />
                {shortFault(rec.fault.type)}
              </Badge>
            )}
          </span>
        </div>

        <p className="trajcard__task" title={rec.task}>
          {injected && rec.fault && baseline ? (
            <>
              <span className="trajcard__blast">
                <ArrowRight size={12} />
              </span>
            </>
          ) : null}
          {rec.task}
        </p>

        <div className="trajcard__chips">
          <StepChips steps={rec.stepTypes} />
        </div>
      </div>

      <div className="trajcard__side">
        <div className="trajcard__meta">
          <span title="Steps">
            <Layers size={13} /> {rec.numSteps}
          </span>
          <span title="Agents">
            <Users size={13} /> {rec.agents.length}
          </span>
          {injected && rec.fault?.originStep != null && (
            <span className="trajcard__origin" title={`Fault injected at step ${rec.fault.originStep}`}>
              <Zap size={13} /> step {rec.fault.originStep}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}
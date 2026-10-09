import { Waypoints, Crosshair, MoveRight } from "lucide-react";
import { Badge } from "../shared/Badge.jsx";
import { stepTypeInfo, humanize } from "../../lib/taxonomy.js";

const STATUS_TONE = {
  changed: "amber",
  added: "cyan",
  removed: "slate",
  same: "slate",
};

function ChainStrip({ propagation }) {
  const ordered = [...(propagation.affectedSteps ?? [])].sort((a, b) => a - b);
  const edgeSet = new Set(
    (propagation.edges ?? []).map(([a, b]) => `${a}->${b}`)
  );

  if (ordered.length === 0) return null;

  return (
    <div className="chainstrip">
      <span className="chainstrip__origin">
        <Crosshair size={12} /> origin
      </span>
      {ordered.map((stepIndex, i) => {
        const node = (propagation.nodes ?? []).find(
          (n) => n.stepIndex === stepIndex
        );
        const info = stepTypeInfo(node?.stepType);
        const isOrigin = stepIndex === propagation.originStep;

        return (
          <span className="chainstrip__group" key={stepIndex}>
            {i > 0 && (
              edgeSet.has(`${ordered[i - 1]}->${stepIndex}`) ? (
                <MoveRight size={14} className="chainstrip__arrow" />
              ) : (
                <span className="chainstrip__dot">·</span>
              )
            )}
            <span
              className={`chainstrip__node ${isOrigin ? "is-origin" : ""}`}
              style={{ "--sc": info.color }}
            >
              <span className="chainstrip__idx">{stepIndex}</span>
              <span className="chainstrip__type">
                {humanize(node?.stepType ?? "")}
              </span>
            </span>
          </span>
        );
      })}
    </div>
  );
}

function NodeRow({ node }) {
  const info = stepTypeInfo(node.stepType);
  const affected = node.status !== "same";
  const tone = STATUS_TONE[node.status] ?? "slate";

  return (
    <li
      className={`chainnode ${affected ? "is-affected" : ""} ${
        node.isOrigin ? "is-origin" : ""
      }`}
      style={{ "--sc": info.color }}
    >
      <span className="chainnode__idx">{node.stepIndex}</span>
      <span className="chainnode__type">{node.stepType}</span>
      {node.agent && <span className="chainnode__agent">{node.agent}</span>}

      <span className="chainnode__tags">
        {node.isOrigin && <Badge tone="red">origin</Badge>}
        {node.isRootCause && <Badge tone="red">root cause</Badge>}
        <Badge tone={tone}>{node.status}</Badge>
      </span>

      {affected && node.changes?.length > 0 && (
        <ul className="chainnode__changes">
          {node.changes.map((change) => (
            <li key={change.field}>
              <span className="chainnode__field">{change.field}</span>
              <span className="chainnode__before">{change.before}</span>
              <span className="chainnode__arrow">→</span>
              <span className="chainnode__after">{change.after}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function PropagationChain({ replay }) {
  const propagation = replay?.propagation;
  if (!propagation) return null;

  const nodes = propagation.nodes ?? [];
  const affected = propagation.affectedSteps ?? [];
  const outcome = propagation.outcome ?? {};
  const origin = propagation.originStep;

  return (
    <section className="detail-section chain">
      <header className="detail-section__head">
        <span className="detail-section__title">
          <Waypoints size={15} /> Propagation chain
        </span>
        {origin != null && (
          <Badge tone="red">origin · step {origin}</Badge>
        )}
        <Badge tone="amber">
          {affected.length}/{nodes.length} steps affected
        </Badge>
        <span className="detail-section__hint">
          {humanize(propagation.faultType ?? "")}
        </span>
      </header>

      <ChainStrip propagation={propagation} />

      <div className="chain__outcome">
        <div className="chain__outcome-cell">
          <span className="chain__outcome-k">baseline</span>
          <span className="chain__outcome-v chain__outcome-v--ok">
            {outcome.baseline?.status ?? "—"}
          </span>
          <span className="chain__outcome-s">
            {outcome.baseline?.success_score?.toFixed?.(1) ?? "—"}
          </span>
        </div>
        <MoveRight size={16} className="chain__outcome-arrow" />
        <div className="chain__outcome-cell">
          <span className="chain__outcome-k">injected</span>
          <span className="chain__outcome-v chain__outcome-v--fail">
            {outcome.injected?.status ?? "—"}
          </span>
          <span className="chain__outcome-s">
            {outcome.injected?.success_score?.toFixed?.(1) ?? "—"}
          </span>
        </div>
      </div>

      <ul className="chainnodes">
        {nodes.map((node) => (
          <NodeRow key={`${node.stepIndex}-${node.stepType}`} node={node} />
        ))}
      </ul>
    </section>
  );
}

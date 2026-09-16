import { Layers, GitBranch, ExternalLink } from "lucide-react";
import { useStore } from "../../data/store.jsx";
import { TrajectoryHeader } from "./TrajectoryHeader.jsx";
import { FaultCard } from "./FaultCard.jsx";
import { CompareView } from "./CompareView.jsx";
import { StepCard } from "./StepCard.jsx";
import { Badge } from "../shared/Badge.jsx";
import { JsonBlock } from "../shared/ValueBlock.jsx";
import { navigate } from "../../hooks.js";
import { alignSequences, stepFieldChanges } from "../../lib/diff.js";

function DetailInner({ id }) {
  const { data, byId } = useStore();
  const rec = byId.get(id);
  if (!rec)
    return (
      <div className="page page--error">
        <p>
          trajectory not found — <button className="link" onClick={() => navigate("/")}>back</button>
        </p>
      </div>
    );

  const baseline = rec.baseId ? byId.get(rec.baseId) : null;
  const isInjected = rec.source === "INJECTED";

  // Compare context (used by both CompareView and FaultCard).
  let cmpPairs = null;
  let cmpChanges = null;
  let injRootIdx = -1;
  if (isInjected && baseline) {
    cmpPairs = alignSequences(baseline.steps, rec.steps);
    cmpChanges = new Map();
    for (const p of cmpPairs) {
      if (p.b != null && p.i != null) {
        cmpChanges.set(p.i, stepFieldChanges(baseline.steps[p.b], rec.steps[p.i]));
      }
    }
    injRootIdx = rec.steps.findIndex((s) => s.isRootCause);
  }

  const rootInjectedStep =
    (injRootIdx >= 0 && rec.steps[injRootIdx]) ||
    rec.steps.find((s) => s.index === rec.fault?.originStep);
  const rootPair = cmpPairs?.find((p) => p.i != null && rec.steps[p.i] === rootInjectedStep);
  const rootChanges = rootPair?.i != null ? cmpChanges.get(rootPair.i) : null;

  const otherVariants = isInjected
    ? data.injected.filter((r) => r.baseId === rec.baseId && r.id !== rec.id)
    : data.injected.filter((r) => r.baseId === rec.id);

  return (
    <div className="page">
      <TrajectoryHeader rec={rec} baseline={baseline} />

      {isInjected && rootInjectedStep && (
        <FaultCard
          fault={rec.fault}
          baselineStep={
            rootPair?.b != null
              ? baseline?.steps[rootPair.b]
              : baseline?.steps.find((s) => s.index === rec.fault?.originStep)
          }
          injectedStep={rootInjectedStep}
          changes={rootChanges}
        />
      )}

      {isInjected && baseline ? (
        <CompareView baseline={baseline} injected={rec} />
      ) : (
        <section className="detail-section">
          <header className="detail-section__head">
            <span className="detail-section__title">
              <Layers size={15} /> Execution timeline
            </span>
            <Badge tone="cyan">{rec.numSteps} steps</Badge>
          </header>
          <div className="timeline timeline--single">
            {rec.steps.map((step, i) => (
              <StepCard key={i} step={step} mode="baseline" isRootCause={false} defaultOpen={i === 0} />
            ))}
          </div>
        </section>
      )}

      {otherVariants.length > 0 && (
        <section className="detail-section">
          <header className="detail-section__head">
            <span className="detail-section__title">
              <GitBranch size={15} /> Related trajectories
            </span>
            <span className="detail-section__hint">
              {isInjected ? "other variants of the same baseline" : "fault-injected variants of this baseline"}
            </span>
          </header>
          <div className="related-list">
            {otherVariants.slice(0, 24).map((r) => (
              <button key={r.id} className="related-item" onClick={() => navigate({ name: "detail", id: r.id })}>
                <span className="related-item__id">{r.id}</span>
                {r.fault && (
                  <span className="related-item__type">
                    <Badge tone="amber">{r.fault.type}</Badge>
                  </span>
                )}
                <ExternalLink size={12} />
              </button>
            ))}
            {otherVariants.length > 24 && (
              <button
                className="related-item related-item--more"
                onClick={() => navigate(`/?q=${rec.baseId ?? rec.id}&source=INJECTED`)}
              >
                show all {otherVariants.length}
                <ExternalLink size={12} />
              </button>
            )}
          </div>
        </section>
      )}

      <JsonBlock value={rec} label="full trajectory record" />
    </div>
  );
}

export default function DetailView({ id }) {
  return <DetailInner id={id} />;
}
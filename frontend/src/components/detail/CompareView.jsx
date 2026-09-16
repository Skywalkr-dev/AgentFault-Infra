import { useMemo, useState } from "react";
import { Expand, Shrink, GitCompareArrows, Sparkles, Bug } from "lucide-react";
import { Badge } from "../shared/Badge.jsx";
import { StepCard, StepSlot } from "./StepCard.jsx";
import { alignSequences, stepFieldChanges } from "../../lib/diff.js";

export function CompareView({ baseline, injected }) {
  const [forceOpen, setForceOpen] = useState(null); // true = expand all, false = collapse all

  const pairs = useMemo(
    () => alignSequences(baseline.steps, injected.steps),
    [baseline, injected]
  );

  const changesByInjectedIdx = useMemo(() => {
    const map = new Map();
    for (const p of pairs) {
      if (p.b != null && p.i != null) {
        map.set(p.i, stepFieldChanges(baseline.steps[p.b], injected.steps[p.i]));
      }
    }
    return map;
  }, [pairs, baseline, injected]);

  const injRootIdx = injected.steps.findIndex((s) => s.isRootCause);
  const rootPairIdx = injRootIdx >= 0
    ? pairs.findIndex((p) => p.i === injRootIdx)
    : -1;

  const expanded = (pairIdx, side) =>
    forceOpen === true ? true : forceOpen === false ? false : pairIdx === rootPairIdx || (pairIdx === 0 && side === "left");

  const changedSteps = changesByInjectedIdx.size;
  const addedSteps = pairs.filter((p) => p.b === null).length;
  const removedSteps = pairs.filter((p) => p.i === null).length;

  return (
    <section className="compare">
      <header className="compare__head">
        <span className="compare__title">
          <GitCompareArrows size={15} />
          Baseline vs injected
        </span>
        <span className="compare__legend">
          <Badge tone="amber">{changedSteps} changed</Badge>
          <Badge tone="cyan">{addedSteps} added</Badge>
          <Badge tone="slate">{removedSteps} removed</Badge>
        </span>
        <span className="compare__controls">
          <button className="btn-icon" title="Expand all steps" onClick={() => setForceOpen(true)}>
            <Expand size={15} />
          </button>
          <button className="btn-icon" title="Collapse all steps" onClick={() => setForceOpen(false)}>
            <Shrink size={15} />
          </button>
        </span>
      </header>

      <div className="compare__grid">
        <div className="compare__col">
          <div className="compare__colhead compare__colhead--base">
            <span className="compare__coltag">
              <Sparkles size={13} /> baseline
            </span>
            <Badge tone="cyan">NATURAL</Badge>
            <span className="compare__colcount">{baseline.numSteps} steps</span>
          </div>
          <div className="timeline">
            {pairs.map((p, idx) =>
              p.b != null ? (
                <StepCard
                  key={idx}
                  step={baseline.steps[p.b]}
                  mode="baseline"
                  isRootCause={p.i != null && p.i === injRootIdx}
                  defaultOpen={expanded(idx, "left")}
                  forceOpen={forceOpen}
                />
              ) : (
                <StepSlot key={idx} kind="removed" type={injected.steps[p.i].type} />
              )
            )}
          </div>
        </div>

        <div className="compare__col">
          <div className="compare__colhead compare__colhead--inj">
            <span className="compare__coltag">
              <Bug size={13} /> injected
            </span>
            <Badge tone="amber">INJECTED</Badge>
            <span className="compare__colcount">{injected.numSteps} steps</span>
          </div>
          <div className="timeline">
            {pairs.map((p, idx) =>
              p.i != null ? (
                <StepCard
                  key={idx}
                  step={injected.steps[p.i]}
                  mode="injected"
                  changes={changesByInjectedIdx.get(p.i) ?? null}
                  isRootCause={p.i === injRootIdx}
                  defaultOpen={expanded(idx, "right")}
                  forceOpen={forceOpen}
                />
              ) : (
                <StepSlot key={idx} kind="added" type={baseline.steps[p.b].type} />
              )
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
import { Boxes, Layers, Bug, Activity, Sparkles } from "lucide-react";

export function StatsBar({ meta }) {
  if (!meta) return null;
  const { counts } = meta;
  const represented = meta.faultTaxonomy.filter((t) => t.represented).length;
  const stats = [
    { icon: Boxes, label: "Trajectories", value: counts.baseline + counts.injected, hint: "total" },
    { icon: Sparkles, label: "Baseline", value: counts.baseline, hint: "natural" },
    { icon: Layers, label: "Injected", value: counts.injected, hint: "faulty" },
    { icon: Bug, label: "Fault types", value: `${represented}/${meta.faultTaxonomy.length}`, hint: "represented", accent: represented < meta.faultTaxonomy.length },
    { icon: Activity, label: "Steps", value: counts.steps, hint: "in dataset" },
  ];
  return (
    <div className="statsbar">
      {stats.map((s) => (
        <div className={`statcard ${s.accent ? "statcard--warn" : ""}`} key={s.label}>
          <s.icon size={15} className="statcard__icon" />
          <div className="statcard__body">
            <div className="statcard__value">{s.value}</div>
            <div className="statcard__label">
              {s.label} <span className="statcard__hint">{s.hint}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
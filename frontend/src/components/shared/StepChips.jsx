import { stepTypeInfo } from "../../lib/taxonomy.js";

// Compact row of step-type chips for cards / headers.
export function StepChips({ steps, max = 9, size = "sm" }) {
  const shown = steps.slice(0, max);
  const rest = steps.length - shown.length;
  return (
    <span className={`stepchips stepchips--${size}`}>
      {shown.map((type, i) => {
        const info = stepTypeInfo(type);
        return (
          <span key={i} className="stepchip" style={{ "--chip-c": info.color }}>
            {type}
          </span>
        );
      })}
      {rest > 0 && <span className="stepchip stepchip--more">+{rest}</span>}
    </span>
  );
}
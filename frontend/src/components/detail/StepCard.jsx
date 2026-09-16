import { useState, useEffect } from "react";
import { ChevronDown, Crosshair, ArrowRight, Minus } from "lucide-react";
import { Badge } from "../shared/Badge.jsx";
import { ValueTree, JsonBlock } from "../shared/ValueBlock.jsx";
import { stepTypeInfo } from "../../lib/taxonomy.js";
import { valueShort } from "../../lib/diff.js";

// ---- field diff rows (shown on injected steps that differ from baseline) ----
export function DiffRows({ changes }) {
  if (!changes || changes.length === 0) return null;
  return (
    <div className="diffrows">
      <div className="diffrows__title">
        <Badge tone="amber" className="diffrows__badge">
          diff · {changes.length}
        </Badge>
        <span>changed vs baseline</span>
      </div>
      {changes.map((c, idx) => {
        const path = c.path && c.path.length ? `.${c.path.join(".")}` : "";
        const label = c.field === "input" || c.field === "output" ? c.label + path : c.label;
        return (
          <div className="diffrow" key={idx}>
            <span className="diffrow__path">{label}</span>
            <span className="diffrow__before" title={typeof c.before === "string" ? c.before : undefined}>
              {valueShort(c.before, 180)}
            </span>
            <ArrowRight size={12} className="diffrow__arrow" />
            <span className="diffrow__after" title={typeof c.after === "string" ? c.after : undefined}>
              {valueShort(c.after, 180)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function Field({ label, children, absent }) {
  return (
    <div className={`field ${absent ? "field--absent" : ""}`}>
      <span className="field__label">{label}</span>
      <span className="field__value">{children || <em className="field__none">—</em>}</span>
    </div>
  );
}

export function StepCard({
  step,
  mode = "injected",
  changes = null,
  isRootCause = false,
  defaultOpen = false,
  forceOpen = null,
  annotation = null,
}) {
  const [open, setOpen] = useState(defaultOpen);
  // Sync with external expand-all / collapse-all controls.
  useEffect(() => {
    if (forceOpen != null) setOpen(forceOpen);
  }, [forceOpen]);
  const info = stepTypeInfo(step.type);
  const status = step.status ?? "—";

  const statusTone =
    status === "FAILED_RECOVERY"
      ? "orange"
      : status === "error"
        ? "red"
        : status === "success" || status === "SUCCESS"
          ? "green"
          : "slate";

  return (
    <div
      className={`stepcard stepcard--${mode} ${isRootCause ? "stepcard--root" : ""} ${step.metadata?.is_root_cause ? "stepcard--root" : ""}`}
      style={{ "--sc": info.color }}
    >
      <div className="stepcard__head" onClick={() => setOpen(!open)} role="button" tabIndex={0}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(!open); } }}>
        <span className="stepcard__idx">{step.type === "TOOL_RESULT" ? "res" : step.index ?? step.step_index ?? "·"}</span>
        <span className="stepcard__type" title={step.type}>{step.type}</span>
        {step.agent && <span className="stepcard__pill stepcard__pill--agent">{step.agent}</span>}
        {step.tool && <span className="stepcard__pill stepcard__pill--tool">{step.tool}</span>}
        {annotation && <span className="stepcard__annotation">{annotation}</span>}
        <span className="stepcard__spacer" />
        {isRootCause && <span className="stepcard__root-tag"><Crosshair size={11} /> root</span>}
        {status && <Badge tone={statusTone}>{status}</Badge>}
        {changes && changes.length > 0 && <Badge tone="amber" className="stepcard__chgcount">{changes.length}Δ</Badge>}
        <ChevronDown size={15} className={`stepcard__caret ${open ? "is-open" : ""}`} />
      </div>

      {open && (
        <div className="stepcard__body">
          {isRootCause && (
            <div className="rootstrip">
              <span className="rootstrip__badge">
                <Crosshair size={12} /> ROOT CAUSE
              </span>
              <span className="rootstrip__text">fault injected at this step — output diverges from baseline</span>
            </div>
          )}
          {changes && <DiffRows changes={changes} />}

          <div className="stepcard__fields">
            <Field label="agent" absent={!step.agent}>{step.agent}</Field>
            <Field label="tool" absent={!step.tool}>{step.tool}</Field>
            {step.type !== "TOOL_RESULT" && (
              <Field label="input" absent={step.input == null}>
                {step.input != null && step.input !== "" && (
                  <div className="field__box">
                    {typeof step.input === "string" ? (
                      <pre className="v-pre">{step.input}</pre>
                    ) : (
                      <ValueTree value={step.input} />
                    )}
                  </div>
                )}
              </Field>
            )}
            <Field label="output" absent={step.output == null}>
              {step.output != null && step.output !== "" && (
                <div className="field__box">
                  {typeof step.output === "string" ? (
                    <pre className="v-pre">{step.output}</pre>
                  ) : (
                    <ValueTree value={step.output} />
                  )}
                </div>
              )}
            </Field>
            <Field label="docs" absent={step.docs == null && step.type !== "RETRIEVAL"}>
              {step.docs != null && (
                <div className="field__box">
                  <div className="field__docs-count">{Array.isArray(step.docs) ? `${step.docs.length} document${step.docs.length === 1 ? "" : "s"}` : "documents"}</div>
                  {Array.isArray(step.docs) && step.docs.length > 0 && <ValueTree value={step.docs} />}
                </div>
              )}
            </Field>
            <Field label="status" absent={!status}>{status}</Field>
            <Field label="metadata" absent={!step.metadata || Object.keys(step.metadata).length === 0}>
              {step.metadata && Object.keys(step.metadata).length > 0 && <ValueTree value={step.metadata} />}
            </Field>
          </div>

          <JsonBlock value={step} label="raw step record" />
        </div>
      )}
    </div>
  );
}

// Ghost slot used for added/removed steps in the side-by-side comparison.
export function StepSlot({ kind = "removed", type }) {
  return (
    <div className={`stepslot stepslot--${kind}`}>
      {kind === "removed" ? <Minus size={13} /> : <ArrowRight size={13} />}
      <span className="stepslot__type">{type ?? "step"}</span>
      <span className="stepslot__label">{kind === "removed" ? "removed in injected" : "not present in baseline"}</span>
    </div>
  );
}
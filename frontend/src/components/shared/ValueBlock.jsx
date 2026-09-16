import { useState } from "react";
import { ChevronDown, Braces, Eye, EyeOff } from "lucide-react";
import { jsonPretty } from "../../lib/format.js";

// Pretty recursive renderer for arbitrary structured values.
export function ValueTree({ value, name, depth = 0, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const isObj = value != null && typeof value === "object";
  const isArray = Array.isArray(value);

  if (!isObj) {
    return <Primitive value={value} />;
  }

  const keys = Object.keys(value);
  const collapsible = depth >= 0 && (isArray ? value.length > 4 : keys.length > 0);
  const expanded = collapsible ? open : true;

  return (
    <div className="vnode" style={{ "--vd": depth }}>
      {isArray ? (
        <div className="vrow vrow--label">
          <span className={`vkey ${collapsible ? "is-clickable" : ""}`} onClick={() => collapsible && setOpen(!open)}>
            {collapsible && <ChevronDown size={12} className={`vtoggle ${open ? "is-open" : ""}`} />}
            [{value.length}]
          </span>
          <span className="vbrace">array</span>
        </div>
      ) : (
        <div className="vrow vrow--label">
          <span className={`vkey ${collapsible ? "is-clickable" : ""}`} onClick={() => collapsible && setOpen(!open)}>
            {collapsible && <ChevronDown size={12} className={`vtoggle ${open ? "is-open" : ""}`} />}
            {keys.length === 0 ? "∅" : `{${keys.slice(0, 3).join(", ")}${keys.length > 3 ? ", …" : ""}}`}
          </span>
          <span className="vbrace">object</span>
        </div>
      )}
      {expanded && (
        <div className="vchildren">
          {(isArray ? value.map((v, i) => ({ k: i, v })) : Object.entries(value).map(([k, v]) => ({ k, v }))).map(
            ({ k, v }) => (
              <div className="vrow" key={String(k)}>
                <span className="vkey">{isArray ? `#${k}` : k}</span>
                <span className="vsep">:</span>
                <span className="vval">
                  <ValueTree value={v} depth={depth + 1} />
                </span>
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}

function Primitive({ value }) {
  if (value === null || value === undefined) return <span className="v-null">null</span>;
  if (typeof value === "string") {
    const inline = value.includes("\n");
    return (
      <span className="v-str">
        {inline ? <PreBlock text={value} /> : <span className="v-str-q">"{shorten(value, 220)}"</span>}
      </span>
    );
  }
  if (typeof value === "number") return <span className="v-num">{value}</span>;
  if (typeof value === "boolean") return <span className="v-bool">{String(value)}</span>;
  return <span className="v-mut">{String(value)}</span>;
}

function shorten(s, n) {
  return s.length <= n ? s : s.slice(0, n) + "…";
}

function PreBlock({ text }) {
  return <pre className="v-pre">{text}</pre>;
}

// Small inline JSON toggle  (view raw structured record toggle)
export function JsonBlock({ value, label = "raw record", defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="jsonblock">
      <button className="jsonblock__toggle" onClick={() => setOpen(!open)}>
        {open ? <EyeOff size={13} /> : <Eye size={13} />}
        <Braces size={13} />
        <span>{label}</span>
        <ChevronDown size={13} className={`vtoggle ${open ? "is-open" : ""}`} />
      </button>
      {open && <pre className="jsonblock__pre">{jsonPretty(value)}</pre>}
    </div>
  );
}
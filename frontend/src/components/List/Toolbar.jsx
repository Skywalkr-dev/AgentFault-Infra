import { Search, X, SlidersHorizontal } from "lucide-react";
import { STEP_TYPE_ORDER, FAULT_GROUPS } from "../../lib/taxonomy.js";

function Select({ label, value, onChange, options, placeholder }) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {(options ?? []).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Toolbar({ filters, setFilter, reset, meta }) {
  const faultTypes = meta?.faultTaxonomy?.filter((t) => t.represented) ?? [];
  const typeOptions = [
    { value: "ALL", label: "All fault types" },
    ...faultTypes
      .filter((t) => filters.group === "ALL" || t.group === filters.group)
      .map((t) => ({ value: t.type, label: `${t.type} (${t.count})` })),
  ];

  return (
    <div className="toolbar">
      <div className="toolbar__row toolbar__row--search">
        <div className="searchbox">
          <Search size={15} className="searchbox__icon" />
          <input
            value={filters.q}
            onChange={(e) => setFilter("q", e.target.value)}
            placeholder="Search trajectories…"
            aria-label="Search trajectories"
          />
          {filters.q && (
            <button className="searchbox__clear" onClick={() => setFilter("q", "")} aria-label="Clear search">
              <X size={14} />
            </button>
          )}
        </div>

        <div className="toolbar__chips" role="tablist" aria-label="Source">
          {[
            { value: "ALL", label: "All" },
            { value: "BASELINE", label: "Baseline" },
            { value: "INJECTED", label: "Injected" },
          ].map((s) => (
            <button
              key={s.value}
              role="tab"
              aria-selected={filters.source === s.value}
              className={`pill ${filters.source === s.value ? "pill--active" : ""}`}
              onClick={() => setFilter("source", s.value)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      <div className="toolbar__row toolbar__row--filters">
        <SlidersHorizontal size={13} className="toolbar__filters-icon" />
        <Select
          label="Group"
          value={filters.group}
          onChange={(v) => setFilter("group", v)}
          options={[
            { value: "ALL", label: "All groups" },
            ...Object.entries(FAULT_GROUPS).map(([id, g]) => ({ value: id, label: g.label })),
          ]}
        />
        <Select
          label="Fault type"
          value={filters.type}
          onChange={(v) => setFilter("type", v)}
          options={typeOptions}
        />
        <Select
          label="Step type"
          value={filters.step}
          onChange={(v) => setFilter("step", v)}
          options={[
            { value: "ALL", label: "All step types" },
            ...STEP_TYPE_ORDER.map((s) => ({ value: s, label: s })),
          ]}
        />
        <Select
          label="Outcome"
          value={filters.outcome}
          onChange={(v) => setFilter("outcome", v)}
          options={[
            { value: "ALL", label: "Success / failure" },
            { value: "SUCCESS", label: "SUCCESS" },
            { value: "FAIL", label: "FAIL" },
          ]}
        />
        <Select
          label="Agent"
          value={filters.agent}
          onChange={(v) => setFilter("agent", v)}
          options={[
            { value: "ALL", label: "All agents" },
            ...(meta?.agents ?? []).map((a) => ({ value: a, label: a })),
          ]}
        />
        <button className="btn btn--ghost btn--xs" onClick={reset} title="Reset all filters">
          <X size={13} /> Reset
        </button>
      </div>
    </div>
  );
}
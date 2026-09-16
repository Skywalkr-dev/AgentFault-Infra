import { useMemo, useState, useEffect } from "react";
import { FilterX } from "lucide-react";
import { useStore } from "../../data/store.jsx";
import { StatsBar } from "../StatsBar.jsx";
import { Toolbar } from "./Toolbar.jsx";
import { TaxonomyPanel } from "./TaxonomyPanel.jsx";
import { TrajectoryCard } from "./TrajectoryCard.jsx";

const GROUP_PREFIX = { PLAN: "PLAN_", TOOL: "TOOL_", KNOW: "KNOW_", MA: "MA_", CTRL: "CTRL_", SEC: "SEC_" };

const DEFAULT_FILTERS = {
  q: "",
  source: "ALL",
  group: "ALL",
  type: "ALL",
  step: "ALL",
  outcome: "ALL",
  agent: "ALL",
};

function matchesFilters(rec, f) {
  if (f.source !== "ALL" && rec.source !== f.source) return false;

  if (f.step !== "ALL" && !rec.stepTypes.includes(f.step)) return false;
  if (f.outcome !== "ALL" && rec.outcome.status !== f.outcome) return false;
  if (f.agent !== "ALL" && !rec.agents.includes(f.agent)) return false;

  // Fault-type / group visibility:
  //  - injected records match their own fault
  //  - baseline records match when they host a variant of the fault type (pair view)
  if (f.type !== "ALL") {
    if (rec.source === "INJECTED" && rec.fault?.type !== f.type) return false;
    if (rec.source === "BASELINE" && !(rec.variantFaults ?? []).includes(f.type)) return false;
  } else if (f.group !== "ALL") {
    if (rec.source === "INJECTED" && rec.fault?.group !== f.group) return false;
    if (rec.source === "BASELINE") {
      const hasGroup = (rec.variantFaults ?? []).some((t) => t.startsWith(GROUP_PREFIX[f.group]));
      if (!hasGroup) return false;
    }
  }

  if (f.q) {
    const q = f.q.toLowerCase();
    const haystack = [
      rec.id,
      rec.baseId,
      rec.task,
      rec.source,
      rec.fault?.type,
      rec.fault?.operator,
      rec.agents.join(" "),
      rec.stepTypes.join(" "),
      rec.outcome.status,
      (rec.variantFaults ?? []).join(" "),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(q)) return false;
  }

  return true;
}

function ListViewInner({ route }) {
  const { data, byId } = useStore();
  const meta = data.meta;
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS });

  const activeCount = Object.values(filters).filter((v) => v !== "ALL" && v !== "").length;

  // Seed search from the URL query (?q=…)
  useEffect(() => {
    const q = route.params.get("q") || "";
    setFilters((f) => ({ ...DEFAULT_FILTERS, q }));
  }, [route.params.get("q")]);

  const filtered = useMemo(() => {
    const all = [...data.baseline, ...data.injected];
    const list = all.filter((r) => matchesFilters(r, filters));
    list.sort((a, b) => {
      if (a.outcome.status !== b.outcome.status) return a.outcome.status === "FAIL" ? -1 : 1;
      if (b.numSteps !== a.numSteps) return b.numSteps - a.numSteps;
      return a.id.localeCompare(b.id);
    });
    return list;
  }, [data, filters]);

  const setFilter = (k, v) => setFilters((f) => ({ ...f, [k]: v }));
  const reset = () => setFilters({ ...DEFAULT_FILTERS });

  return (
    <div className="page">
      <StatsBar meta={meta} />

      <Toolbar
        filters={filters}
        setFilter={setFilter}
        reset={reset}
        meta={meta}
      />

      <TaxonomyPanel
        meta={meta}
        selectedType={filters.type}
        selectedGroup={filters.group}
        onSelectType={(v) => setFilter("type", v)}
        onSelectGroup={(v) => setFilter("group", v)}
      />

      <section className="results">
        <div className="results__head">
          <h2 className="results__title">Trajectories</h2>
          <span className="results__count">
            {filtered.length.toLocaleString()} of {(data.baseline.length + data.injected.length).toLocaleString()}
            {activeCount > 0 && <em>· {activeCount} filter{activeCount > 1 ? "s" : ""} active</em>}
          </span>
        </div>

        {filtered.length === 0 ? (
          <div className="empty">
            <FilterX size={28} />
            <p>No trajectories match the current filters.</p>
            <button className="btn btn--ghost" onClick={reset}>
              Clear filters
            </button>
          </div>
        ) : (
          <div className="grid">
            {filtered.map((rec) => (
              <TrajectoryCard key={rec.id} rec={rec} baseline={rec.source === "INJECTED" ? byId.get(rec.baseId) : null} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default function ListView(props) {
  return <ListViewInner {...props} />;
}